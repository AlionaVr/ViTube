# 0013. Liked videos: a list read from likes

**Status:** accepted · 2026-11-12

**Context.** YouTube shows a user's likes as a private playlist, Liked videos (`/playlist?list=LL`): newest like
first, a cover, a count, a card on the Playlists page. ViTube already stores each like as a row of
`video_reactions` with `rated_at`, which changes only when the rating changes.

**Decision.**

- Liked videos is not a `playlists` row: `GET /api/me/liked/items` reads the user's likes (`value = like`),
  `rated_at DESC, video_id DESC`, keyset paging. Liking adds a video, taking the like back removes it, a like
  after a dislike or after "none" puts it on top.
- `GET /api/me/liked` gives what the header and the card show: the count, the cover and the date of the newest
  like. The client adds the title "Liked videos" and "Private".
- The list and the count apply the view policy (`watchable`: ready and `viewable`) when they are read, as the
  history and playlists do (ADR 0012): a video that turns private or hidden leaves both and comes back with
  access. A lost video gives no hint that it still exists (ADR 0004), so the count is not of all likes.
- Index `(user_id, rated_at, video_id)` serves the list; its `user_id` prefix also serves the cascade from
  `users`, so it replaces `ix_video_reactions_user_id`. Not partial (`WHERE value = 1`): asyncpg sends the value
  as a parameter, and a generic plan can't use a partial index for it.
- Guests have no Liked videos (401).

**Alternatives.**

- A playlist of kind `liked`, written on every like: the Playlists module would serve it as it is, but each rating
  writes twice, the two can drift, and the playlist's limit of videos would cap likes.
- The count of all likes, as `playlists.video_count` counts all items: one join less, but "5 videos" over 4 rows,
  and the number tells that a hidden video still exists.

**Consequences.**

- ➕ One source of truth: a like and Liked videos can't disagree.
- ➕ No write on the rating path; the list costs one indexed read.
- ➖ The count is a `count(*)` over the user's likes, not a stored number: it grows with the user's likes.
- ➖ Liked videos can't be reordered, renamed or shared.
