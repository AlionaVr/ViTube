# 0005. Auth: server-side sessions in Redis + CSRF

**Status:** accepted · 2026-11-04

**Context.** `auth_request` relies on cookies (`<video>` can't send an `Authorization` header). Logout and bans must
work immediately.

**Decision.**

- **Session.** Random 256-bit id in a cookie: `HttpOnly; SameSite=Lax`, plus `Secure` when `COOKIE_SECURE=true`.
- **Storage.** Redis stores an HMAC of the id → user, role, CSRF token, timestamps.
- **Fixation.** A new id is issued on every login.
- **Timeouts.** Idle and absolute.
- **Logout.** Deletes the session.
- **Ban or password change.** Deletes all of the user's sessions.
- **CSRF**, three layers:
    - `SameSite=Lax`;
    - `X-CSRF-Token` header on every unsafe method;
    - `Origin` check.
    - GET never changes state.
- **Passwords.** Argon2; rate limits on login and signup; one generic "wrong login or password" error.
- **XSS.** HttpOnly cookie, React escaping (no `dangerouslySetInnerHTML`), CSP.

**Alternatives.** JWT (access + refresh) in cookies: stateless, but tokens can't be revoked early, it needs a refresh
flow, and it still needs CSRF protection.

**Consequences.**

- ➕ Instant logout and ban; fast check in `auth_request`.
- ➖ Server state, but Redis is already in the stack.
- ➖ On plain HTTP (test VM by IP) `Secure` is off; README explains HTTPS.
