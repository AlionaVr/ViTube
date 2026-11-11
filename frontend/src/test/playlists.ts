import type { MyPlaylist, Playlist, PlaylistItem } from '../playlists/types'
import { summary } from './videos'

const ID = (n: number) => `0193a5c2-0000-7000-8000-${String(n).padStart(12, '0')}`

/** A playlist as the API sends it; `n` makes the id and title unique. */
export function playlist(n: number, overrides: Partial<Playlist> = {}): Playlist {
  return {
    id: ID(n),
    title: `Playlist ${n}`,
    description: '',
    visibility: 'private',
    kind: 'user',
    video_count: 0,
    thumbnail_url: null,
    owner: { handle: 'openmovieclub', name: 'Open Movie Club', avatar_url: null },
    created_at: '2026-11-01T10:00:00Z',
    updated_at: new Date().toISOString(),
    ...overrides,
  }
}

export function mine(n: number, contains: boolean | null, overrides: Partial<Playlist> = {}) {
  return { ...playlist(n, overrides), contains_video: contains } satisfies MyPlaylist
}

export function item(n: number): PlaylistItem {
  return { video: summary(n), added_at: '2026-11-02T10:00:00Z' }
}
