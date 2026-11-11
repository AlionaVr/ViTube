import type { Page, VideoSummary } from '../videos/types'

const DAY_MS = 24 * 3600 * 1000

/** A list item as the API sends it; `n` makes the id and title unique. */
export function summary(n: number, overrides: Partial<VideoSummary> = {}): VideoSummary {
  return {
    id: `video-${String(n).padStart(5, '0')}`,
    title: `Video ${n}`,
    thumbnail_url: `/media/thumbs/${n}.jpg`,
    duration_sec: 33,
    view_count: 1_000,
    created_at: new Date(Date.now() - 3 * DAY_MS).toISOString(),
    channel: { handle: 'openmovieclub', name: 'Open Movie Club', avatar_url: null },
    ...overrides,
  }
}

export function page<T>(items: T[], next_cursor: string | null = null): Page<T> {
  return { items, next_cursor }
}
