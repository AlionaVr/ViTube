// Types from the API (schema.d.ts).
import type { components } from '../api/schema'

export type Rating = components['schemas']['Rating']

/** A video in a list: home grid, Up next, search. */
export type VideoSummary = components['schemas']['VideoSummary']

export type Category = components['schemas']['Category']

/** The watch page: the video and what this viewer did with it. */
export type Video = components['schemas']['VideoDetail']

export interface Page<T> {
  items: T[]
  next_cursor: string | null
}
