import type { Liked, LikedItem } from '../liked/api'
import { ANNA } from './api'
import { summary } from './videos'

/** Anna's Liked videos as the API sends them: the cover and the date come from the newest like. */
export function liked(overrides: Partial<Liked> = {}): Liked {
  return {
    video_count: 2,
    thumbnail_url: '/media/thumbs/1.jpg',
    updated_at: new Date().toISOString(),
    owner: { handle: ANNA.handle, name: ANNA.handle, avatar_url: null },
    ...overrides,
  }
}

export function likedItem(n: number): LikedItem {
  return { video: summary(n), liked_at: '2026-11-02T10:00:00Z' }
}
