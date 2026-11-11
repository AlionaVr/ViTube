import type { Playlist } from './types'

/** As on YouTube: Watch later opens at list=WL, any other playlist at its id. */
export function playlistUrl(playlist: Pick<Playlist, 'id' | 'kind'>): string {
  return `/playlist?list=${playlist.kind === 'watch_later' ? 'WL' : playlist.id}`
}
