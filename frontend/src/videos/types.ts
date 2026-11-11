// Types from the API (schema.d.ts). The watch page's are hand-written until it reads the API.
import type { components } from '../api/schema'
import type { Channel } from '../channels/types'

export type Rating = 'like' | 'dislike' | 'none'

/** A video in a list: home grid, Up next, search. */
export type VideoSummary = components['schemas']['VideoSummary']

export type Category = components['schemas']['Category']

/** The watch page. */
export interface Video extends Omit<VideoSummary, 'channel'> {
  description: string
  media_url: string
  like_count: number
  my_rating: Rating
  comment_count: number
  channel: Channel
}

export interface Page<T> {
  items: T[]
  next_cursor: string | null
}
