// In-memory stand-in for the backend: answers like the API will (pages, 401 for guests, 404).
// Deleted once the real endpoints exist; only the */api.ts modules import it.
import { ApiError, type User } from '../api/client'
import { fetchMe } from '../auth/hooks'
import type { Channel, ChannelSummary } from '../channels/types'
import type { Comment, CommentSort } from '../comments/types'
import type { Page, Rating, Video, VideoSummary } from '../videos/types'
import {
  CHANNELS,
  type ChannelKey,
  INITIAL_SUBSCRIPTIONS,
  mediaDuration,
  mediaUrl,
  type MockVideo,
  thumbnailUrl,
  VIDEOS,
} from './catalog'
import { generateComments, type MockComment } from './comments'
import { seededRandom } from './random'

const LATENCY_MS = import.meta.env.MODE === 'test' ? 0 : 400
const NOW = Date.now()
const HOUR_MS = 3600 * 1000

function delay(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, LATENCY_MS))
}

// ---- Viewer: the real session, as the API will read it from the cookie.

/** Waits like the network, then asks who is signed in. No auth backend (offline dev): a guest, as in the UI. */
async function session(): Promise<User | null> {
  await delay()
  try {
    return await fetchMe()
  } catch {
    return null
  }
}

function requireViewer(user: User | null): User {
  if (!user) throw new ApiError(401, 'Sign in required')
  return user
}

// ---- Catalog with stable ids.

interface Entry extends MockVideo {
  id: string
  likes: number
}

const ID_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
const idRandom = seededRandom('vitube')
const ENTRIES: Entry[] = VIDEOS.map((video) => ({
  ...video,
  id: Array.from({ length: 11 }, () => ID_CHARS[Math.floor(idRandom() * 64)]).join(''),
  likes: Math.floor(video.views * (0.015 + idRandom() * 0.035)),
}))

/** Tests open a demo video by its title: the feed no longer lists them. */
export function demoVideoId(title: string): string {
  const entry = ENTRIES.find((e) => e.title === title)
  if (!entry) throw new Error(`No demo video "${title}"`)
  return entry.id
}

function findEntry(id: string): Entry {
  const entry = ENTRIES.find((e) => e.id === id)
  if (!entry) throw new ApiError(404, 'Video not found')
  return entry
}

function channelSummary(key: ChannelKey): ChannelSummary {
  const { handle, name } = CHANNELS[key]
  return { handle, name, avatar_url: null }
}

function channelKey(handle: string): ChannelKey {
  const key = (Object.keys(CHANNELS) as ChannelKey[]).find((k) => CHANNELS[k].handle === handle)
  if (!key) throw new ApiError(404, 'Channel not found')
  return key
}

// ---- Mutable state: what the viewer did in this tab.

interface State {
  ratings: Map<string, Rating>
  subscriptions: Set<ChannelKey>
  commentRatings: Map<string, Rating>
  comments: Map<string, { top: MockComment[]; replies: Map<string, MockComment[]> }>
}

function initialState(): State {
  return {
    ratings: new Map(),
    subscriptions: new Set(INITIAL_SUBSCRIPTIONS),
    commentRatings: new Map(),
    comments: new Map(),
  }
}

let state = initialState()

/** Tests start from a clean state. */
export function resetMockServer(): void {
  state = initialState()
}

function paginate<T>(items: T[], cursor: string | null, size: number): Page<T> {
  const start = cursor ? Number(cursor) : 0
  const end = start + size
  return { items: items.slice(start, end), next_cursor: end < items.length ? String(end) : null }
}

function rating(user: User | null, map: Map<string, Rating>, id: string): Rating {
  return user ? (map.get(id) ?? 'none') : 'none'
}

/** Base counts exclude the viewer; their own like is added here. */
function withRating<T extends { like_count: number }>(item: T, myRating: Rating) {
  return {
    ...item,
    like_count: item.like_count + (myRating === 'like' ? 1 : 0),
    my_rating: myRating,
  }
}

// ---- Videos.

function toSummary(entry: Entry): VideoSummary {
  return {
    id: entry.id,
    title: entry.title,
    thumbnail_url: thumbnailUrl(entry.media, entry.frame),
    duration_sec: mediaDuration(entry.media),
    view_count: entry.views,
    created_at: new Date(NOW - entry.age * HOUR_MS).toISOString(),
    channel: channelSummary(entry.channel),
  }
}

function toVideo(entry: Entry, user: User | null): Video {
  const subscribed = user !== null && state.subscriptions.has(entry.channel)
  const channel: Channel = {
    ...channelSummary(entry.channel),
    subscriber_count: CHANNELS[entry.channel].subscribers + (subscribed ? 1 : 0),
    is_subscribed: subscribed,
  }
  const { top, replies } = commentsOf(entry)
  const replyTotal = [...replies.values()].reduce((sum, list) => sum + list.length, 0)
  return {
    ...toSummary(entry),
    ...withRating({ like_count: entry.likes }, rating(user, state.ratings, entry.id)),
    description: entry.description,
    media_url: mediaUrl(entry.media),
    comment_count: top.length + replyTotal,
    channel,
  }
}

export async function getVideo(id: string): Promise<Video> {
  const user = await session()
  return toVideo(findEntry(id), user)
}

export async function listRelated(id: string, cursor: string | null): Promise<Page<VideoSummary>> {
  await delay()
  const current = findEntry(id)
  // Same channel first, then the same film, then the rest.
  const score = (e: Entry) =>
    e.channel === current.channel ? 0 : e.media === current.media ? 1 : 2
  const related = ENTRIES.filter((e) => e.id !== id).sort((a, b) => score(a) - score(b))
  return paginate(related.map(toSummary), cursor, 12)
}

export async function rateVideo(
  id: string,
  myRating: Rating,
): Promise<{ like_count: number; my_rating: Rating }> {
  requireViewer(await session())
  const entry = findEntry(id)
  state.ratings.set(id, myRating)
  return withRating({ like_count: entry.likes }, myRating)
}

// ---- Channels.

export async function listSubscriptions(): Promise<ChannelSummary[]> {
  const user = await session()
  return user ? [...state.subscriptions].map(channelSummary) : []
}

export async function setSubscribed(
  handle: string,
  subscribed: boolean,
): Promise<{ subscriber_count: number; is_subscribed: boolean }> {
  requireViewer(await session())
  const key = channelKey(handle)
  if (subscribed) state.subscriptions.add(key)
  else state.subscriptions.delete(key)
  return {
    subscriber_count: CHANNELS[key].subscribers + (subscribed ? 1 : 0),
    is_subscribed: subscribed,
  }
}

// ---- Comments.

function commentsOf(entry: Entry) {
  let comments = state.comments.get(entry.id)
  if (!comments) {
    const publishedAt = NOW - entry.age * HOUR_MS
    comments = generateComments(
      entry.id,
      entry.media,
      channelSummary(entry.channel),
      entry.views,
      publishedAt,
      NOW,
    )
    state.comments.set(entry.id, comments)
  }
  return comments
}

function toComment(comment: MockComment, user: User | null): Comment {
  return withRating(comment, rating(user, state.commentRatings, comment.id))
}

function findComment(id: string): MockComment {
  for (const { top, replies } of state.comments.values()) {
    const found =
      top.find((c) => c.id === id) ?? [...replies.values()].flat().find((c) => c.id === id)
    if (found) return found
  }
  throw new ApiError(404, 'Comment not found')
}

export async function listComments(
  videoId: string,
  sort: CommentSort,
  cursor: string | null,
): Promise<Page<Comment>> {
  const user = await session()
  const { top } = commentsOf(findEntry(videoId))
  // Like YouTube: the viewer's own comments come first, then by likes or by date.
  const mine = (c: MockComment) => (user && c.author.handle === user.handle ? 0 : 1)
  const order = (a: MockComment, b: MockComment) =>
    mine(a) - mine(b) ||
    (sort === 'top' ? b.like_count - a.like_count : b.published_at.localeCompare(a.published_at))
  return paginate(
    [...top].sort(order).map((c) => toComment(c, user)),
    cursor,
    10,
  )
}

export async function listReplies(
  commentId: string,
  cursor: string | null,
): Promise<Page<Comment>> {
  const user = await session()
  findComment(commentId)
  const replies = [...state.comments.values()].find((c) => c.replies.has(commentId))?.replies
  return paginate(
    (replies?.get(commentId) ?? []).map((c) => toComment(c, user)),
    cursor,
    10,
  )
}

export async function addComment(
  videoId: string,
  text: string,
  parentId: string | null,
): Promise<Comment> {
  const user = requireViewer(await session())
  const trimmed = text.trim()
  if (!trimmed) throw new ApiError(422, 'Comment is empty')
  const entry = findEntry(videoId)
  const { top, replies } = commentsOf(entry)
  const comment: MockComment = {
    id: `${videoId}-c${Date.now().toString(36)}`,
    author: { handle: user.handle, name: user.handle, avatar_url: null },
    by_owner: false,
    text: trimmed,
    published_at: new Date().toISOString(),
    like_count: 0,
    reply_count: 0,
  }
  if (parentId) {
    const parent = findComment(parentId)
    comment.id = `${parentId}-r${Date.now().toString(36)}`
    replies.set(parentId, [...(replies.get(parentId) ?? []), comment])
    parent.reply_count += 1
  } else {
    top.unshift(comment)
  }
  return toComment(comment, user)
}

export async function rateComment(
  id: string,
  myRating: Rating,
): Promise<{ like_count: number; my_rating: Rating }> {
  requireViewer(await session())
  const comment = findComment(id)
  state.commentRatings.set(id, myRating)
  return withRating({ like_count: comment.like_count }, myRating)
}
