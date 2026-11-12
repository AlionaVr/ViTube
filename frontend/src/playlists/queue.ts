import type { VideoSummary } from '../videos/types'

/** What plays after the current video of a list. */
export type Next =
  /** Behind a page not loaded yet. */
  { status: 'pending' } | { status: 'video'; video: VideoSummary } | { status: 'end' }

/**
 * The list in its order: where `current` is and what follows it. `complete`: no more pages.
 * A video that isn't in the list is followed by the first one.
 */
export function inOrder(
  videos: VideoSummary[],
  current: string,
  complete: boolean,
): { position: number | null; next: Next } {
  const at = videos.findIndex((video) => video.id === current)
  const position = at < 0 ? null : at
  if (position === null && !complete) return { position, next: { status: 'pending' } }
  const following = videos.at(at + 1) // the first one when `current` isn't there
  if (following) return { position, next: { status: 'video', video: following } }
  return { position, next: complete ? { status: 'end' } : { status: 'pending' } }
}
