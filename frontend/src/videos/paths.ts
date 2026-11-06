// YouTube-style URLs.

export function watchUrl(id: string): string {
  return `/watch?v=${encodeURIComponent(id)}`
}

export function channelUrl(handle: string): string {
  return `/@${handle}`
}
