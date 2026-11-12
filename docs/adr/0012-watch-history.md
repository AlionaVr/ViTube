# 0012. Watch history: one row per video, saved by the player

**Status:** accepted · 2026-11-12

**Context.** A signed-in user sees what they watched (`/feed/history`), a red bar on each thumbnail shows where
they stopped, and a video resumes there. The player has to save its position often enough to resume, without a
write per second. Public lists (home, search, channel) are the same for every viewer.

**Decision.**

- One row per user and video in `watch_history`: `position_sec`, `watched_at`. A save is one upsert
  (`INSERT … ON CONFLICT DO UPDATE`), so parallel saves can't add a second row, and watching again moves the
  video to the top.
- The player saves when playback starts, pauses and ends, every 10 s while playing, and when the viewer leaves
  the video: another video, another page, or a closing tab (`fetch` with `keepalive`). The server cuts the position
  to the video's length and allows 120 saves a minute per user.
- Progress bars come from their own request, `GET /api/me/history/progress?v=…` (up to 100 ids). Each thumbnail
  asks for its video; the client sends the ids asked for in one tick as one request (as a GraphQL DataLoader does).
  The player's saves update the bars in the client's cache, so they aren't fetched again.
- The list applies the view policy (`viewable`) when it is read: a video that turns private or hidden leaves the
  history and comes back with access. Only the user (remove, clear) and cascades delete rows.
- Pause: `users.history_paused`. While it is on, saves change nothing; the client also doesn't save while it
  doesn't know the setting yet.
- Guests keep no history.

**Alternatives.**

- The position as a field of every card (`VideoSummary`), as YouTube sends it: one request instead of two, but
  home, search and channel lists would read the session and differ per viewer, and every list service changes.
- A row per watch: a full log, but the history must then pick one row per video, and the table grows with every
  watch.
- Positions buffered in Redis and written later: fewer writes, more parts. One row update per 10 s per watching
  user is fine for Postgres at this scale.

**Consequences.**

- ➕ The history and the bars are read by key; the table grows with the videos watched, not with watch time.
- ➕ Public lists stay the same for every viewer.
- ➖ A signed-in viewer's page of cards takes a second request.
- ➖ A save changes the indexed `watched_at`, so it is not a HOT update: one dead row per save for autovacuum.
- ➖ If the browser dies before `pagehide`, the saved position can be up to 10 s behind.
- ➖ Another open tab shows its bars as they were until it reloads.
