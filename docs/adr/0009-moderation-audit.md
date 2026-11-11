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
- Moderators don't act on their own videos or comments: another moderator decides.
- Deleting a comment is soft: the row stays as evidence, lists and counters leave it out, and a thread's first comment
  takes its replies along. Everyone who writes to a thread (a reply, a delete) locks its first comment first, so a
  reply racing a delete either goes with the thread or is refused, and counters stay exact.
- An action is one transaction: lock the target, change it, close its open reports, write the audit entry. Either
  all of it happens or none of it. A repeated action that changes nothing writes no entry.
- `audit_log` records every moderator and admin action: who, what, target, when, details (jsonb). It is
  append-only: the app's DB role may not update or delete it (ADR 0010).
- Account status, set by admins (API and moderation page) and the CLI: `banned` (no sign-in, sessions end, content
  stays), `terminated` (the same, and the channel's videos are restricted like hidden ones, by status, with no
  change to each video), `active` (reinstated). Admins can't restrict themselves or another admin. How a ban holds:
  ADR 0005. *(Amended 2026-11-11: bans had no UI and channels no termination.)*
- Roles are managed via the CLI, with no UI. The seed creates demo admin and moderator accounts. The CLI logs its
  changes with source `cli`, the shell user and the admin named by `--by` (claimed, not proven: shell access is
  the boundary).

**Consequences.**

- ➕ Moderator actions are traceable, and the trail can't be rewritten through the app.
- ➖ No role-management UI (deliberate scope cut).
