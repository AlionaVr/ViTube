// YouTube-style URLs.

/** A video in a list: `list` is LL, WL or a playlist id, as on YouTube. */
export function watchUrl(id: string, queue?: { list: string }): string {
  const params = new URLSearchParams({ v: id })
  if (queue) params.set('list', queue.list)
  return `/watch?${params}`
}

export function channelUrl(handle: string): string {
  return `/@${handle}`
}
