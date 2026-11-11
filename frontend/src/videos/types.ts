// Types from the API (schema.d.ts).
import type { components } from '../api/schema'

export type Rating = components['schemas']['Rating']

/** A video in a list: home grid, Up next, search. */
export type VideoSummary = components['schemas']['VideoSummary']

export type Category = components['schemas']['Category']

/** The watch page: the video and what this viewer did with it. */
export type Video = components['schemas']['VideoDetail']

/** The owner's view: upload dialog and Studio. Any status, with the reason a processing failed. */
export type OwnVideo = components['schemas']['VideoOut']

export type Visibility = components['schemas']['Visibility']

export type VideoStatus = components['schemas']['VideoStatus']

export interface Page<T> {
  items: T[]
  next_cursor: string | null
}
