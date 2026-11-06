# ViTube — YouTube clone

FastAPI + PostgreSQL + MinIO + Celery + React. Deployed with `./install.sh` (Docker Compose).

- Plan, requirements, roadmap: `docs/plan.md`
- Decisions: `docs/adr/`. ADRs are binding. If a change contradicts one, stop and cite its number.

## Commands

- Stack: `docker compose up -d --build --wait` (without `.env`: add `--env-file .env.example`).
- Backend (`backend/`): `uv run ruff check .`, `uv run pyright`, `uv run pytest` (needs Docker: tests start Postgres and Redis via testcontainers).
- Migrations: `docker compose run --rm migrate alembic <cmd>`. See the `add-migration` skill.
- Frontend (`frontend/`): `npm run dev` (proxies `/api` to the stack), `npm run lint`, `npm run format:check`, `npm test`, `npm run build`.
- CI (`.github/workflows/ci.yml`): the checks above, plus a deploy via `install.sh`, `alembic check` and migrations down/up.

## Workflow

- **Plan first.**
    - Use plan mode for any task with 3+ steps or an architectural choice.
    - Write the plan to `tasks/todo.md` as checkboxes; check in before building; tick items as you go.
    - If something goes sideways, stop and re-plan. Don't push on.
- **Subagents.**
    - Hand research, exploration and parallel analysis to subagents to keep the main context clean.
    - One task per subagent.
- **Lessons.**
    - After any correction from the user, add the pattern and a rule that prevents it to `tasks/lessons.md`.
    - Read it at session start.
- **Verify before done.**
    - Never call a task done without proof: run tests, check logs, show it works.
    - Ask: "Would a staff engineer approve this?"
- **Elegance, balanced.**
    - For non-trivial changes, ask "is there a simpler, cleaner way?"
    - If a fix feels hacky, redo it properly.
    - Skip this for obvious fixes.
- **Bugs.**
    - Given a bug report, just fix it: use logs, errors and failing tests.
    - Find the root cause. No temporary patches.
- **Report.** Give a short high-level summary of what changed at each step.

## Principles

- Simplicity first: the smallest change that solves the problem.
- Minimal impact: touch only what's needed.
- Senior standards: root causes, no shortcuts, no dead code.
- Repo text (code comments, docs, configs) is English, short and plain. A comment says *why*, in one line.

## Git

The user commits. After each logical step, list the changed files and propose Conventional Commit messages, e.g.
`feat(upload): stream file to MinIO`. One logical change per commit.
