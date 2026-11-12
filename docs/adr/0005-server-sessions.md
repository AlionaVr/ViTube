# 0005. Auth: server-side sessions in Redis + CSRF

**Status:** accepted · 2026-11-04

**Context.** `auth_request` relies on cookies (`<video>` can't send an `Authorization` header). Logout and bans must
work immediately.

**Decision.**

- **Session.** Random 256-bit id in a cookie: `HttpOnly; SameSite=Lax`, plus `Secure` when `COOKIE_SECURE=true`.
- **Storage.** Redis stores an HMAC of the id → user id, CSRF token, creation time. Not the role: it is read from
  the DB on every request, so a role change applies at once. A cache comes only if the Stage 10 load test needs it.
  *(Amended 2026-11-06: the role was in Redis.)*
- **Fixation.** A new id is issued on every login.
- **Timeouts.** Idle and absolute.
- **Logout.** Deletes the session.
- **Durability.** Redis keeps an append-only log, fsync every second: a crash loses at most 1 s, so a logout is not
  undone. With snapshots only, a crash brought back sessions deleted since the last snapshot (up to an hour).
- **Ban or password change.** Deletes all of the user's sessions. *(Amended 2026-11-11: how a ban holds;
  2026-11-12: advisory locks, and no session from before a ban works again.)*
    - The DB decides, not Redis: every request reads the user's status, and a banned user's request runs as a
      guest's and ends its session. So a session the cleanup misses (made during the ban, made before the index
      existed, or Redis down) works nowhere.
    - A ban also sets the user's `sessions_valid_after`: sessions started before it are refused for good, so a
      reinstated account doesn't bring back one the cleanup missed.
    - No write commits after a ban: an unsafe request takes its user's advisory lock, shared, until it commits; a
      status or role change takes it exclusive first, so it waits for writes under way, and later ones queue
      behind it and see it. Not row locks (`FOR KEY SHARE` against `FOR UPDATE`): new row share locks pass a
      waiting `FOR UPDATE`, so a user who keeps a write in flight could hold their ban off for good. A request
      that commits twice (upload) checks again before its last commit.
    - Cleanup: Redis keeps each user's session keys in a sorted set, scored by creation time; a ban deletes the
      keys it reads. Sessions past the absolute timeout leave the set on the next login.
- **CSRF**, three layers:
    - `SameSite=Lax`;
    - `X-CSRF-Token` header on every unsafe method;
    - `Origin` check.
    - GET never changes state.
- **Passwords.** Argon2; one generic "wrong login or password" error.
- **Rate limits**, counted atomically in Redis:
    - signup: per IP;
    - login: per IP; per email + IP (5 / 15 min), so one IP can't lock the owner out; per email from all IPs
      (100 / 15 min) against guessing from many IPs. Trade-off: 20+ IPs can still block new sign-ins to an
      account for 15 min; browsers already signed in keep working.
    - Emails are ASCII (international domains as punycode): Python and Postgres lowercase them the same, so
      a case variant can't get its own counter.
- **XSS.** HttpOnly cookie, React escaping (no `dangerouslySetInnerHTML`), CSP.

**Alternatives.** JWT (access + refresh) in cookies: stateless, but tokens can't be revoked early, it needs a refresh
flow, and it still needs CSRF protection.

**Consequences.**

- ➕ Instant logout and ban; fast check in `auth_request`.
- ➖ Server state, but Redis is already in the stack.
- ➖ On plain HTTP (test VM by IP) `Secure` is off; README explains HTTPS.
