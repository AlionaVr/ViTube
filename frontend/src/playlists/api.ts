// Playlists API.
import { api, unwrap } from '../api/client'
import type { Page } from '../videos/types'
import type { MyPlaylist, Playlist, PlaylistCreate, PlaylistItem, PlaylistUpdate } from './types'

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

/** Only the given fields change. Throws ApiError 400 for Watch later. */
export function updatePlaylist(id: string, body: PlaylistUpdate): Promise<Playlist> {
  return unwrap(
    api.PATCH('/api/playlists/{playlist_id}', { params: { path: { playlist_id: id } }, body }),
  )
}

export function deletePlaylist(id: string): Promise<void> {
  return unwrap(
    api.DELETE('/api/playlists/{playlist_id}', { params: { path: { playlist_id: id } } }),
  )
}

/** Just before another video of the playlist, or to the end (`before` null). */
export function moveInPlaylist(id: string, videoId: string, before: string | null): Promise<void> {
  return unwrap(
    api.PATCH('/api/playlists/{playlist_id}/items/{public_id}', {
      params: { path: { playlist_id: id, public_id: videoId } },
      body: { before },
    }),
  )
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

/** A channel's Playlists tab: public ones only. Throws ApiError 404 for an unknown handle. */
export function listChannelPlaylists(
  handle: string,
  cursor: string | null,
): Promise<Page<Playlist>> {
  return unwrap(
    api.GET('/api/channels/{handle}/playlists', {
      params: { path: { handle }, query: { cursor } },
    }),
  )
}

/** The viewer's playlists, newest first; with a video, each says whether it holds it. */
export function listMyPlaylists(
  videoId: string | null,
  cursor: string | null,
): Promise<Page<MyPlaylist>> {
  return unwrap(api.GET('/api/me/playlists', { params: { query: { video: videoId, cursor } } }))
}

/** Whether the video is in any of the viewer's playlists. Throws ApiError 401 for a guest. */
export async function getSaved(videoId: string): Promise<boolean> {
  const answer = await unwrap(
    api.GET('/api/videos/{public_id}/saved', { params: { path: { public_id: videoId } } }),
  )
  return answer.saved
}
