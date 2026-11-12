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
  if (following) return { position, next: toPlay(following) }
  return { position, next: complete ? { status: 'end' } : { status: 'pending' } }
}

/** A new shuffle's seed, for `shuffle=`. */
export function newSeed(): string {
  return Math.random().toString(36).slice(2, 10)
}

/** FNV-1a, 32 bits: a key that looks random but is the same for the same text. */
function hash(text: string): number {
  let key = 0x811c9dc5
  for (let i = 0; i < text.length; i++) {
    key ^= text.charCodeAt(i)
    key = Math.imul(key, 0x01000193)
  }
  return key >>> 0
}

/** The seed's order. Each video's place hangs on its own key, so removing one moves no other. */
export function shuffled(videos: VideoSummary[], seed: string): VideoSummary[] {
  return videos
    .map((video) => ({ video, key: hash(`${seed}:${video.id}`) }))
    .sort((a, b) => a.key - b.key || a.video.id.localeCompare(b.video.id))
    .map(({ video }) => video)
}

/**
 * A shuffled list: the first page in the seed's order, turned so `current` plays at `index`
 * (from 1). So a shuffle turned on mid-list starts at the current video and plays all the others.
 * After a video that isn't on the first page comes the order's first one.
 */
export function inShuffle(
  firstPage: VideoSummary[],
  current: string,
  seed: string,
  index: number,
): { videos: VideoSummary[]; position: number | null; next: Next } {
  const order = shuffled(firstPage, seed)
  const at = order.findIndex((video) => video.id === current)
  if (at < 0) {
    return { videos: order, position: null, next: order[0] ? toPlay(order[0]) : { status: 'end' } }
  }
  const count = order.length
  const position = Number.isInteger(index) && index >= 1 && index <= count ? index - 1 : 0
  const start = (at - position + count) % count
  const videos = [...order.slice(start), ...order.slice(0, start)]
  const following = videos.at(position + 1)
  return { videos, position, next: following ? toPlay(following) : { status: 'end' } }
}

function toPlay(video: VideoSummary): Next {
  return { status: 'video', video }
}
