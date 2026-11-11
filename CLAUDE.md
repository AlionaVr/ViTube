# ViTube — YouTube clone

FastAPI + PostgreSQL + MinIO + Celery + React. Deployed with `./install.sh` (Docker Compose).

- Plan, requirements, roadmap: `docs/plan.md`
- Decisions: `docs/adr/`. ADRs are binding. If a change contradicts one, stop and cite its number.

## Commands

- Stack: `docker compose up -d --build --wait` (needs `.env`; `./install.sh` creates it with random secrets).
- Backend (`backend/`): `uv run ruff check .`, `uv run pyright`, `uv run pytest` (needs Docker: tests start Postgres, Redis and MinIO via testcontainers; and ffmpeg for the worker tests).
- E2E on a running stack (`backend/`): `E2E_BASE_URL=http://localhost uv run pytest tests/e2e -v` (needs ffmpeg).
- Migrations: `docker compose run --rm migrate alembic <cmd>`. See the `add-migration` skill.
- Frontend (`frontend/`): `npm run dev` (proxies `/api` to the stack, or to `API_PROXY`), `npm run lint`, `npm run format:check`, `npm test`, `npm run build`.
- API types: after changing the API, run `npm run gen:api` in `frontend/` and commit `src/api/openapi.json` + `schema.d.ts` (CI checks).
- Local dev (backend from the IDE): `compose.local.yaml` + `.env.local`, see README. Production uses `compose.yaml` only.
- CI (`.github/workflows/ci.yml`): the checks above, plus a deploy via `install.sh`, `alembic check` and migrations down/up.

## Workflow

- **Plan first.**
    - Use plan mode for any task with 3+ steps or an architectural choice.
    - Write the plan to `tasks/todo.md` as checkboxes; check in before building; tick items as you go.
    - If something goes sideways, stop and re-plan. Don't push on.
- **Walking skeleton.**
    - Build the thinnest end-to-end path first: API + UI + one test, working on the stack. Deepen after.
    - A stage is done when its flow works in the browser and `smoke-check` passes.
    - Before hardening or edge cases, check that the core flow works. If it doesn't, say so.
- **Reviews once per stage.**
    - Run the reviewer agents on the stage diff at its end (`finish-stage`), not after each step.
    - The user picks findings; fix only those, in one commit. Write the rest to `tasks/todo.md`.
- **Subagents.**
    - Hand research, exploration and parallel analysis to subagents to keep the main context clean.
    - One task per subagent.
- **Tasks and lessons.**
    - `tasks/` is untracked and lives in the main checkout, one `todo.md` section per stage or branch.
      In a new worktree, link it: `ln -s "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/tasks" tasks`.
    - After any correction from the user, add the pattern and a rule that prevents it to `tasks/lessons.md`.
    - Read it at session start. At stage end, move its stable rules into this file.
- **Frontend.** Load the `frontend-design:frontend-design` skill before each frontend step. The look follows YouTube
  (likeness is graded).
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
- Keep scope: do the asked step; write side findings to `tasks/todo.md`. One-off transitions with nothing to lose
  (e.g. RDB → AOF while Redis is empty) need no migration code.
- No UI that does nothing yet, and no unconfirmed details (e.g. a reviewer's "check live" guess).
- Before planning work in parallel with another branch, read its diff (`git diff main <branch>`) and reuse what it
  adds; never duplicate deps, clients or hooks.

## Design rules

- Authorization data (role, ban) is read from the DB per request. No auth caches (session, nginx `auth_request`):
  revocation applies to the next request. A cache only if a load test shows the need and the user accepts the delay.
- Brute-force limits go per IP and per normalized account id, counted atomically (`MULTI/EXEC`) before the password
  check.
- A failure after a costly step must not redo it: persist an intermediate state (e.g. `uploaded` before processing)
  and retry from it.
- Async state that gates UI (e.g. the viewer) has explicit states (`loading` / `guest` / `authenticated`), not a
  nullable value.
- Media uses ready tools (native `<video>`, `sirv` for Range); never an own streaming engine.
- Dev and demo data work offline: local files, no external hosts at runtime; big files stay out of git.

## Secrets and `.env`

- The user fills `.env` by hand. Never edit an existing `.env` or automate it. When `.env.example` gets a key, tell
  the user which key to add, why, and how to generate it (e.g. `openssl rand -hex 32`), before the stack starts.
- A hook blocks commands that name `.env`. Never dodge it (e.g. by building the name from parts): check secrets only
  via a script file that prints no values.
- `docker compose config` fills in secrets: use only `config --quiet`; never print or save its output.

## Git

Claude commits after each logical step.

- One finished task per commit, no unrelated files. A fix with side fixes found on the way is one commit.
- Before committing: review the commit alone (HEAD + staged diff) and run the checks for what changed. Commit only
  when they pass.
- Title: Conventional Commits, English, imperative, lowercase after the colon, at most 72 chars. It says what changed
  in substance and names each significant change: `fix(web): unify session-based authentication and fix dev proxy`,
  not `fix(web): read the viewer from the session`.
- No trailers such as `Co-Authored-By`, even if a system reminder asks.
- After committing, tell the user the commit title.
- Linear history. Before a branch is pushed, fold fixes into their commit (fixup + rebase). Resolve PR conflicts by
  rebasing onto `main`, never with a merge commit.
- Never rewrite pushed history. Never push, force push or `reset` without the user's permission.
