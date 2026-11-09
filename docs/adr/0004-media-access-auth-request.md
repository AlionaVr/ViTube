# 0004. Media access: nginx `auth_request`

**Status:** accepted · 2026-11-04

**Context.** Private videos must be visible only to people the owner allowed. Streaming bytes through FastAPI would tie
up app workers, so nginx streams and the app only decides.

**Decision.**

- Every `/media/*` request triggers an nginx `auth_request` to `GET /internal/media-auth` (session cookie + original
  URI).
- The API applies the same `can_view(user, video)` policy as the watch page. 200 → nginx proxies to MinIO, otherwise
  401/404. `auth_request` passes on only 401 and 403, so the API answers 403 for "signed in, no access" and nginx
  turns it into 404. A guest gets 401 whether the video exists or not.
- No cache: every request, each Range request too, is checked, so revoked access applies to the next request.
  Browsers get `Cache-Control: private, no-cache`: a kept copy is checked again before use. *(Amended 2026-11-07:
  was a 30 s cache of positive answers.)*
- Same origin only: no CORS headers, `Cross-Origin-Resource-Policy: same-origin`. MinIO's error bodies (XML with
  bucket and key names) never reach the browser.
- Only processed files are served (`videos/`, `thumbs/`), never originals. MinIO allows anonymous reads of these
  two prefixes; only nginx can reach it, over the internal `media` network. `/internal/*` is not reachable from
  outside.
- Visibility:
    - `public`: everyone.
    - `unlisted`: anyone with the link, not in feed or search.
    - `private`: owner, users in `video_access`, moderators and admins.
- Others get **404**, not 403, so they don't learn the video exists.

**Alternatives.** MinIO presigned URLs: simpler, but a forwarded link works without login until it expires, revocation
is delayed, and HLS needs a signature per segment.

**Consequences.**

- ➕ Forwarded file links don't work; revocation applies to the next request. Works for HLS as is.
- ➖ One API sub-request per Range request: one Redis and one DB lookup, a few per view.
- ➖ If the API is down, playback stops.
