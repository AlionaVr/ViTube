# Lessons

Patterns from user corrections. Read at session start.

- Repo text is English, short and plain. Users don't read long text. (2026-11-04)
- Don't run `git commit`. The user commits; propose messages instead. (2026-11-04)
- Commands containing `.env` are blocked by a hook. Put such checks in a script file. (2026-11-04)
- Never dodge that hook (e.g. building the file name from parts). Check secrets only via a script that prints no values. (2026-11-05)
- `docker compose config` fills in secrets from `.env`. Use only `config --quiet`; never print or save its output. (2026-11-05)
