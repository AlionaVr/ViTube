import type { Comment } from '../comments/types'
import type { Page, Video, VideoSummary } from '../videos/types'

const DAY_MS = 24 * 3600 * 1000
const daysAgo = (days: number) => new Date(Date.now() - days * DAY_MS).toISOString()

/** A list item as the API sends it; `n` makes the id and title unique. */
export function summary(n: number, overrides: Partial<VideoSummary> = {}): VideoSummary {
  return {
    id: `video-${String(n).padStart(5, '0')}`,
    title: `Video ${n}`,
    thumbnail_url: `/media/thumbs/${n}.jpg`,
    duration_sec: 33,
    view_count: 1_000,
    created_at: daysAgo(3),
    channel: { handle: 'openmovieclub', name: 'Open Movie Club', avatar_url: null },
    ...overrides,
  }
}

/** The watch page data of a ready public video. */
export function detail(n: number, overrides: Partial<Video> = {}): Video {
  return {
    ...summary(n),
    description: 'A lone girl searches for the baby dragon she once saved.',
    visibility: 'public',
    category: 'film',
    status: 'ready',
    error_message: null,
    media_url: `/media/videos/${n}/720p.mp4`,
    like_count: 120,
    comment_count: 1,
    my_rating: 'none',
    ...overrides,
  }
}

export function comment(n: number, overrides: Partial<Comment> = {}): Comment {
  return {
    id: `0193a5c2-0000-7000-8000-${String(n).padStart(12, '0')}`,
    author: { handle: 'framebyframe', name: 'Frame by Frame', avatar_url: null },
    by_owner: false,
    text: `Comment ${n}`,
    published_at: daysAgo(1),
    like_count: 3,
    my_rating: 'none',
    reply_count: 0,
    ...overrides,
  }
}

export function page<T>(items: T[], next_cursor: string | null = null): Page<T> {
  return { items, next_cursor }
}
