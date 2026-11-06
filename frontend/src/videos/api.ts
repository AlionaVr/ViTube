// Videos API. Reads the demo server for now; each function becomes a request
// (`unwrap(api.GET(...))`, src/api/client.ts) once the backend has the endpoint.
import * as server from '../mocks/server'
import type { Category, Page, Rating, Video, VideoSummary } from './types'

export function listVideos(params: {
  category: string | null
  cursor: string | null
}): Promise<Page<VideoSummary>> {
  return server.listVideos(params)
}

/** Throws ApiError 404 for an unknown or private video. */
export function getVideo(id: string): Promise<Video> {
  return server.getVideo(id)
}

export function listRelated(id: string, cursor: string | null): Promise<Page<VideoSummary>> {
  return server.listRelated(id, cursor)
}

/** Throws ApiError 401 for a guest. */
export function rateVideo(
  id: string,
  rating: Rating,
): Promise<{ like_count: number; my_rating: Rating }> {
  return server.rateVideo(id, rating)
}

export function listCategories(): Promise<Category[]> {
  return server.listCategories()
}
