// Videos API. Requests go through openapi-fetch with types from schema.d.ts (src/api/client.ts).
import { api, unwrap } from '../api/client'
import type { Category, Page, Rating, Video, VideoSummary } from './types'

const video = (id: string) => ({ path: { public_id: id } })

/** The home feed: public videos, newest first; `null` category means all. */
export function listVideos(
  category: Category | null,
  cursor: string | null,
): Promise<Page<VideoSummary>> {
  return unwrap(api.GET('/api/videos', { params: { query: { category, cursor } } }))
}

/** Categories that have public videos, in YouTube's order. */
export function listCategories(): Promise<Category[]> {
  return unwrap(api.GET('/api/categories'))
}

/** Throws ApiError 404 for an unknown video or one this viewer may not watch. */
export function getVideo(id: string): Promise<Video> {
  return unwrap(api.GET('/api/videos/{public_id}', { params: video(id) }))
}

/** Up next: the channel's other videos first, then the newest. */
export function listRelated(id: string, cursor: string | null): Promise<Page<VideoSummary>> {
  return unwrap(
    api.GET('/api/videos/{public_id}/related', { params: { ...video(id), query: { cursor } } }),
  )
}

/** Throws ApiError 401 for a guest. */
export function rateVideo(
  id: string,
  rating: Rating,
): Promise<{ like_count: number; my_rating: Rating }> {
  return unwrap(api.PUT('/api/videos/{public_id}/rating', { params: video(id), body: { rating } }))
}
