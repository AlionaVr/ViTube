// Comments API (see videos/api.ts).
import { api, unwrap } from '../api/client'
import type { Page, Rating } from '../videos/types'
import type { Comment, CommentSort } from './types'

export function listComments(
  videoId: string,
  sort: CommentSort,
  cursor: string | null,
): Promise<Page<Comment>> {
  return unwrap(
    api.GET('/api/videos/{public_id}/comments', {
      params: { path: { public_id: videoId }, query: { sort, cursor } },
    }),
  )
}

/** Replies, oldest first. */
export function listReplies(commentId: string, cursor: string | null): Promise<Page<Comment>> {
  return unwrap(
    api.GET('/api/comments/{comment_id}/replies', {
      params: { path: { comment_id: commentId }, query: { cursor } },
    }),
  )
}

/** Throws ApiError 401 for a guest, 422 for an empty text. */
export function addComment(
  videoId: string,
  text: string,
  parentId: string | null,
): Promise<Comment> {
  return unwrap(
    api.POST('/api/videos/{public_id}/comments', {
      params: { path: { public_id: videoId } },
      body: { text, parent_id: parentId },
    }),
  )
}

/** Throws ApiError 401 for a guest. */
export function rateComment(
  id: string,
  rating: Rating,
): Promise<{ like_count: number; my_rating: Rating }> {
  return unwrap(
    api.PUT('/api/comments/{comment_id}/rating', {
      params: { path: { comment_id: id } },
      body: { rating },
    }),
  )
}
