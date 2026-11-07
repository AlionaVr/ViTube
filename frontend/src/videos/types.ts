// Hand-written until the API exists; then replaced by types from schema.d.ts. snake_case as FastAPI sends it.
import type { Channel, ChannelSummary } from '../channels/types'

export type Rating = 'like' | 'dislike' | 'none'

/** A video in a feed: home grid, Up next, search. */
export interface VideoSummary {
  /** 11-character public id, as in /watch?v=<id>. */
  id: string
  title: string
  thumbnail_url: string
  duration_sec: number
  view_count: number
  published_at: string
  channel: ChannelSummary
  /** Where the viewer stopped last time; null if never watched. */
  last_position_sec: number | null
}

/** The watch page. */
export interface Video extends Omit<VideoSummary, 'channel'> {
  description: string
  media_url: string
  like_count: number
  my_rating: Rating
  comment_count: number
  channel: Channel
}

export interface Category {
  id: string
  name: string
}

export interface Page<T> {
  items: T[]
  next_cursor: string | null
}
