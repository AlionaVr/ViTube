# 0004. Media access: nginx `auth_request`

**Status:** accepted · 2026-11-04

**Context.** Private videos must be visible only to people the owner allowed. Streaming bytes through FastAPI would tie
up app workers, so nginx streams and the app only decides.

**Decision.**

- Every `/media/*` request triggers an nginx `auth_request` to `GET /internal/media-auth` (session cookie + original
  URI).
- The API applies the same `can_view(user, video)` policy as the watch page. 200 → nginx proxies to MinIO, otherwise
  401/404.
- nginx caches positive answers for ~30 s. `/internal/*` is not reachable from outside.
- Visibility:
    - `public`: everyone.
    - `unlisted`: anyone with the link, not in feed or search.
    - `private`: owner, users in `video_access`, moderators and admins.
- Others get **404**, not 403, so they don't learn the video exists.

**Alternatives.** MinIO presigned URLs: simpler, but a forwarded link works without login until it expires, revocation
is delayed, and HLS needs a signature per segment.

**Consequences.**

- ➕ Forwarded file links don't work; revocation is immediate (within the 30 s cache). Works for HLS as is.
- ➖ One API sub-request per Range request (few per view, cheap, cached).
- ➖ If the API is down, playback stops.
