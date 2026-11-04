# 0009. Moderation: reports, hiding, audit log

**Status:** accepted · 2026-11-04

**Context.** The moderation screen needs reports and video hiding. Roles: user, moderator, admin.

**Decision.**

- Roles are nested: `user` ⊂ `moderator` ⊂ `admin`.
- Reports on videos and comments, with a reason enum and text. One open report per user per target.
- Moderator actions:
    - video: hide (with reason), restore, or dismiss the report;
    - comment: delete or dismiss the report.
- A hidden video shows a "Hidden by moderator" banner to its owner. Everyone else gets 404.
- `audit_log` records every moderator and admin action: who, what, target, when, details (jsonb).
- Roles and bans are managed via CLI and API, with no UI. The seed creates demo admin and moderator accounts.

**Consequences.**

- ➕ Moderator actions are traceable.
- ➖ No role-management UI (deliberate scope cut).
