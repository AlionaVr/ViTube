# 0009. Moderation: reports, hiding, audit log

**Status:** accepted · 2026-11-04

**Context.** The moderation screen needs reports and video hiding. Roles: user, moderator, admin.

**Decision.**

- Roles are nested: `user` ⊂ `moderator` ⊂ `admin`.
- Reports on videos and comments, with a reason enum and text. One open report per user per target. The queue
  groups open reports by target, oldest first.
- Moderator actions:
    - video: hide (with reason), restore, or dismiss the report;
    - comment: delete or dismiss the report.
- Hiding is a flag, not a processing status: the worker never writes it, so a video hidden while processing stays
  hidden, and a restore needs no memory of an earlier status.
- A hidden video shows a "Hidden by moderator" banner to its owner and to moderators, who open it to review it.
  Everyone else gets 404, on the page and on `/media`. *(Amended 2026-11-11: moderators got 404 too.)*
  Public lists (feed, search, Up next) leave it out for everyone, moderators too: `LISTED` filters it on top of the
  partial indexes, which keep their predicate (hidden videos are few).
- A hidden video is frozen for everyone, its owner and moderators too: no comments, ratings, views or reports
  until it is restored. A restore doesn't reopen closed reports.
- Moderators don't act on their own videos: another moderator decides.
- An action is one transaction: lock the target, change it, close its open reports, write the audit entry. Either
  all of it happens or none of it. A repeated action that changes nothing writes no entry.
- `audit_log` records every moderator and admin action: who, what, target, when, details (jsonb). It is
  append-only: the app's DB role may not update or delete it (ADR 0010).
- Roles and bans are managed via CLI and API, with no UI. The seed creates demo admin and moderator accounts.

**Consequences.**

- ➕ Moderator actions are traceable, and the trail can't be rewritten through the app.
- ➖ No role-management UI (deliberate scope cut).
