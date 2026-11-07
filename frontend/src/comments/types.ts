// Hand-written until the API exists; then replaced by types from schema.d.ts. snake_case as FastAPI sends it.
import type { ChannelSummary } from '../channels/types'
import type { Rating } from '../videos/types'

export type CommentSort = 'top' | 'new'

export interface Comment {
  id: string
  author: ChannelSummary
  /** The video's owner wrote it: YouTube marks the handle. */
  by_owner: boolean
  text: string
  published_at: string
  like_count: number
  my_rating: Rating
  reply_count: number
}
