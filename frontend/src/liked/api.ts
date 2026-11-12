// Liked videos API: the viewer's likes as a playlist (list=LL).
import { api, unwrap } from '../api/client'
import type { components } from '../api/schema'
import type { Page } from '../videos/types'

export type Liked = components['schemas']['LikedOut']
export type LikedItem = components['schemas']['LikedItem']

/** Count, cover and last change. Throws ApiError 401 for a guest. */
export function getLiked(): Promise<Liked> {
  return unwrap(api.GET('/api/me/liked'))
}

/** Newest like first; only the videos the viewer may watch now. */
export function listLiked(cursor: string | null): Promise<Page<LikedItem>> {
  return unwrap(api.GET('/api/me/liked/items', { params: { query: { cursor } } }))
}
