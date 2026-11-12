# 0014. Sign-in with Google: OpenID Connect code flow through Authlib

**Status:** accepted · 2026-11-12

**Context.** Users want to sign in with their Google account instead of a new password. Sessions, CSRF checks and
bans stay as in ADR 0005. Password sign-up doesn't verify emails, so an email in our table proves nothing about who
owns it.

**Decision.**

- **Protocol.** OpenID Connect authorization code flow with PKCE and a nonce, through Authlib. Fixed endpoints, no
  discovery document: the api calls only Google's token endpoint and its keys (JWKS). The ID token's signature,
  issuer, audience, expiry and nonce are checked. Scope `openid email`: we keep no name or picture.
- **Flow.**
    1. The button opens `GET /api/auth/google/start`: Authlib keeps the state, PKCE verifier and nonce in a signed
       cookie (`google_oauth`: HttpOnly, `SameSite=Lax`, path `/api/auth/google`, 10 min) and redirects to Google.
    2. Google redirects to the web app's page `/auth/google/callback`. It changes nothing.
    3. That page sends `code` and `state` to `POST /api/auth/google/finish`. The state must match the cookie, so a
       code from someone else's sign-in is refused (login CSRF). The response is the user, or 400 / 403 / 409.
- Why the web app takes the callback: sign-in stays a POST, so "GET never changes state" (ADR 0005) and the
  app-wide Origin and CSRF checks still hold, and errors come back as statuses the sign-in form already shows.
- **Identity.** Google's `sub` (`users.google_sub`, unique), never the email. Only an email Google has verified is
  used.
    - Known `sub`: sign in, with a new session id (ADR 0005). A banned or terminated account is refused (403).
    - New `sub` and a free email: a new user with a random handle and no password (`password_hash` NULL; a check
      makes every account keep a password or Google).
    - New `sub` and a taken email: 409, nothing linked or changed. Linking by email would let someone who signed up
      a victim's address with a password first share the victim's account later (pre-hijacking).
    - The stored email isn't updated when it changes at Google.
- **Limits.** `finish` counts as a sign-in per IP; a new account also counts as a sign-up per IP (ADR 0005).
- **State cookie.** Authlib keeps the flow's state in Starlette's `SessionMiddleware`. Its key is derived from
  `SESSION_SECRET` (SHA-256 with a label, not the HMAC that names sessions in Redis), so there is no new secret. It
  lives only during one sign-in; the user's session is still the Redis one.
- **Network.** The api joins `oauth-egress`, a network with internet access (ADR 0008).
- **Off by default.** While `GOOGLE_CLIENT_ID` is empty, `/api/auth/providers` says so and the web app shows no
  Google button.

**Alternatives.**

- Own code over `httpx2`: one request instead of two, but we would write and review the protocol ourselves.
- Google Identity Services (the browser gets the ID token): a script from Google on our pages and a look we don't
  control; the api still needs Google's keys.
- Link accounts by a matching email: easier for a user who signed up with a password, but open to pre-hijacking
  while emails aren't verified. Linking from the signed-in user's settings can come later.
- The callback straight at the api (`GET`): one hop less, but a GET that signs in, and errors as redirects.

**Consequences.**

- ➕ Sign-in without a new password; no password stored for these accounts.
- ➕ Sessions, bans and CSRF work as for password accounts.
- ➖ The api can reach the internet (ADR 0008).
- ➖ Google allows `http` redirect URIs only for `localhost`: a VM reached by IP needs a domain and HTTPS for it.
- ➖ An owner of a password account can't sign in with Google to it.
