// Watch history API: the player saves where it is; the viewer reads their history.
import { api, unwrap } from '../api/client'
import type { components } from '../api/schema'
import type { Page } from '../videos/types'

export type HistoryItem = components['schemas']['HistoryItem']
export type HistorySettings = components['schemas']['HistorySettings']

/** Puts the video on top of the history. `keepalive`: the request outlives a closing tab. */
export async function savePosition(id: string, seconds: number, keepalive = false): Promise<void> {
  await unwrap(
    api.PUT('/api/me/history/{public_id}', {
      params: { path: { public_id: id } },
      body: { position_sec: seconds },
      keepalive,
    }),
  )
}

/** Saved positions by video id; videos never watched are left out. At most 100 ids. */
export function getProgress(ids: string[]): Promise<Record<string, number>> {
  return unwrap(api.GET('/api/me/history/progress', { params: { query: { v: ids } } }))
}

/** Last watched first. Throws ApiError 401 for a guest. */
export function listHistory(cursor: string | null): Promise<Page<HistoryItem>> {
  return unwrap(api.GET('/api/me/history', { params: { query: { cursor } } }))
}

/** Its progress bar goes too. */
export async function removeFromHistory(id: string): Promise<void> {
  await unwrap(api.DELETE('/api/me/history/{public_id}', { params: { path: { public_id: id } } }))
}

export async function clearHistory(): Promise<void> {
  await unwrap(api.DELETE('/api/me/history'))
}

export function getHistorySettings(): Promise<HistorySettings> {
  return unwrap(api.GET('/api/me/history/settings'))
}

/** While paused, new videos don't go to the history; what is there stays. */
export function setHistoryPaused(paused: boolean): Promise<HistorySettings> {
  return unwrap(api.PUT('/api/me/history/settings', { body: { paused } }))
}
