# 0011. Views: one per viewer a day, after real playback

**Status:** accepted · 2026-11-07

**Context.** The view count must not grow from page reloads, repeated or parallel requests, or a script that only
calls the API. Many people can share one IP (NAT).

**Decision.**

- A view needs playback. The client reports `start` when playback begins and `finish` after the threshold:
  min(30 s, video length), at least 1 s (lengths round down: a sub-second video has 0). The server stores the start time in Redis and counts `finish` only if at least
  threshold / 2 has passed (the player's top speed is 2x).
- One view per viewer and video in 24 h: Redis `SET NX EX`, so of parallel requests exactly one counts.
- The viewer is the user id when signed in, whatever the IP, and the IP for guests. Keys are hashed.
- Redis first, then `view_count + 1`: a failed update loses a view, never counts one twice.

**Alternatives.**

- A guest cookie: separates guests behind one NAT, but a script drops it and gets a new view each time.
- Per-IP caps and request limits: more protection, more rules. Not needed at this stage.

**Consequences.**

- ➕ Repeated and parallel reports count once; a single API call counts nothing.
- ➖ Guests behind one NAT count as one viewer: one view per video a day. Signed-in users count apart.
- ➖ A script that waits out the threshold still gets one view per IP or account a day.
