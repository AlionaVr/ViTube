// Videos API. The rest still reads the demo server; each function becomes a request
// (`unwrap(api.GET(...))`, src/api/client.ts) once the backend has the endpoint.
import { api, unwrap } from '../api/client'
import * as server from '../mocks/server'
import type { Page, Rating, Video, VideoSummary } from './types'

/** The home feed: public videos, newest first. */
export function listVideos(cursor: string | null): Promise<Page<VideoSummary>> {
  return unwrap(api.GET('/api/videos', { params: { query: { cursor } } }))
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
