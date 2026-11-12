// YouTube-style URLs.

/** Where a video plays in a list. */
export interface InList {
  /** LL, WL or a playlist id, as on YouTube. */
  list: string
  /** The seed of a shuffled order, and the video's place in it (from 1). */
  shuffle?: string | null
  index?: number
}

export function watchUrl(id: string, queue?: InList): string {
  const params = new URLSearchParams({ v: id })
  if (queue) params.set('list', queue.list)
  if (queue?.shuffle) {
    params.set('shuffle', queue.shuffle)
    params.set('index', String(queue.index ?? 1))
  }
  return `/watch?${params}`
}

export function channelUrl(handle: string): string {
  return `/@${handle}`
}
