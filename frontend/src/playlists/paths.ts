import type { Playlist } from './types'

/** What `list=` names, as on YouTube: the viewer's Watch later (WL), Liked videos (LL), or a playlist. */
export type ListRef = { kind: 'watchLater' } | { kind: 'liked' } | { kind: 'playlist'; id: string }

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/** Null for anything else: no request goes out for it. */
export function parseList(list: string | null): ListRef | null {
  if (list === 'WL') return { kind: 'watchLater' }
  if (list === 'LL') return { kind: 'liked' }
  return list && UUID.test(list) ? { kind: 'playlist', id: list } : null
}

/** The `list=` of a stored playlist: Watch later is WL, any other its id. */
export function listParam(playlist: Pick<Playlist, 'id' | 'kind'>): string {
  return playlist.kind === 'watch_later' ? 'WL' : playlist.id
}

export function playlistUrl(playlist: Pick<Playlist, 'id' | 'kind'>): string {
  return `/playlist?list=${listParam(playlist)}`
}
