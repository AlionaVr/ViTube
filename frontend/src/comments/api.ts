// Comments API. Reads the demo server for now; see videos/api.ts.
import * as server from '../mocks/server'
import type { Page, Rating } from '../videos/types'
import type { Comment, CommentSort } from './types'

export function listComments(
  videoId: string,
  sort: CommentSort,
  cursor: string | null,
): Promise<Page<Comment>> {
  return server.listComments(videoId, sort, cursor)
}

/** Replies, oldest first. */
export function listReplies(commentId: string, cursor: string | null): Promise<Page<Comment>> {
  return server.listReplies(commentId, cursor)
}

/** Throws ApiError 401 for a guest, 422 for an empty text. */
export function addComment(
  videoId: string,
  text: string,
  parentId: string | null,
): Promise<Comment> {
  return server.addComment(videoId, text, parentId)
}

/** Throws ApiError 401 for a guest. */
export function rateComment(
  id: string,
  rating: Rating,
): Promise<{ like_count: number; my_rating: Rating }> {
  return server.rateComment(id, rating)
}
