# 0010. DB roles: the app gets data access only

**Status:** accepted · 2026-11-06

**Context.** The app connected as the Postgres superuser. One SQL injection would be enough to drop tables or run
shell commands in the DB container (`COPY … FROM PROGRAM`).

**Decision.**

- Two roles:
    - the superuser (`POSTGRES_USER`) is used only by the one-shot `migrate` job: migrations, then
      `python -m app.db.roles`;
    - `vitube_app` (`POSTGRES_APP_PASSWORD`) is used by api and worker.
- `vitube_app` may `SELECT, INSERT, UPDATE, DELETE` and use sequences. No DDL, no `TRUNCATE`, no access to
  `alembic_version`. `audit_log` is insert and read only (ADR 0009). Timeouts: `statement_timeout` 30 s,
  `idle_in_transaction_session_timeout` 60 s. *(Amended 2026-11-11: audit_log.)*
- A manual `alembic` run (not the `migrate` job) skips the role setup: run the job after it, or a recreated table
  keeps the default grants until the next deploy.
- The setup is idempotent and runs on every deploy:
    - grants on existing objects, so an existing volume works;
    - default privileges for objects that later migrations create;
    - the password is set each time: to rotate it, change `.env` and redeploy.
- Tests run the app as `vitube_app`, so a missing grant fails the tests.

**Alternatives.**

- A separate non-superuser owner for migrations: one more role and secret, while only the one-shot job uses the
  superuser.
- Row-level security: not needed; access rules live in the service layer (`can_view`).

**Consequences.**

- ➕ An injection can only touch rows the app can touch anyway.
- ➖ One more secret in `.env`. Migrations run through the `migrate` job, not from the IDE.
