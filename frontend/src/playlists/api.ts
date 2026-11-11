// Playlists API.
import { api, unwrap } from '../api/client'
import type { Page } from '../videos/types'
import type { MyPlaylist, Playlist, PlaylistCreate, PlaylistItem } from './types'

/** Throws ApiError 404 for an unknown playlist or someone else's private one. */
export function getPlaylist(id: string): Promise<Playlist> {
  return unwrap(api.GET('/api/playlists/{playlist_id}', { params: { path: { playlist_id: id } } }))
}

/** The viewer's Watch later. Throws ApiError 401 for a guest. */
export function getWatchLater(): Promise<Playlist> {
  return unwrap(api.GET('/api/me/watch-later'))
}

/** The videos this viewer may watch, in order. */
export function listItems(id: string, cursor: string | null): Promise<Page<PlaylistItem>> {
  return unwrap(
    api.GET('/api/playlists/{playlist_id}/items', {
      params: { path: { playlist_id: id }, query: { cursor } },
    }),
  )
}

export function createPlaylist(body: PlaylistCreate): Promise<Playlist> {
  return unwrap(api.POST('/api/playlists', { body }))
}

/** Add to the end, or remove. Both are idempotent. */
export function setInPlaylist(id: string, videoId: string, saved: boolean): Promise<void> {
  const params = { params: { path: { playlist_id: id, public_id: videoId } } }
  return unwrap(
    saved
      ? api.PUT('/api/playlists/{playlist_id}/items/{public_id}', params)
      : api.DELETE('/api/playlists/{playlist_id}/items/{public_id}', params),
  )
}

/** The viewer's playlists, newest first; with a video, each says whether it holds it. */
export function listMyPlaylists(
  videoId: string | null,
  cursor: string | null,
): Promise<Page<MyPlaylist>> {
  return unwrap(api.GET('/api/me/playlists', { params: { query: { video: videoId, cursor } } }))
}
