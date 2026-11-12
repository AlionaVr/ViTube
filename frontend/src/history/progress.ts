import { useQuery } from '@tanstack/react-query'

import { useViewer } from '../viewer/useViewer'
import { getProgress } from './api'
import { historyKeys } from './hooks'

const MAX_IDS = 100 // the server's limit per request
/** Stopped this close to the end: the video counts as watched and starts over, as on YouTube. */
const END_MARGIN_SEC = 5

interface Waiter {
  resolve: (seconds: number | null) => void
  reject: (error: unknown) => void
}

let queue = new Map<string, Waiter[]>()

/** Sends every id asked for in one tick as one request, as a GraphQL DataLoader does. */
function flush() {
  const batch = queue
  queue = new Map()
  const ids = [...batch.keys()]
  for (let start = 0; start < ids.length; start += MAX_IDS) {
    const chunk = ids.slice(start, start + MAX_IDS)
    const settle = (each: (waiter: Waiter, id: string) => void) =>
      chunk.forEach((id) => batch.get(id)!.forEach((waiter) => each(waiter, id)))
    getProgress(chunk).then(
      (positions) => settle((waiter, id) => waiter.resolve(positions[id] ?? null)),
      (error: unknown) => settle((waiter) => waiter.reject(error)),
    )
  }
}

function loadProgress(id: string): Promise<number | null> {
  return new Promise((resolve, reject) => {
    if (queue.size === 0) setTimeout(flush)
    queue.set(id, [...(queue.get(id) ?? []), { resolve, reject }])
  })
}

/**
 * Where the signed-in viewer stopped in a video, in seconds; null if never watched. Each
 * thumbnail asks for its own; the loader joins them. The player's saves update it in place,
 * so it never goes stale by itself.
 */
export function useWatchProgress(videoId: string) {
  const viewer = useViewer()
  return useQuery({
    queryKey: historyKeys.progress(videoId),
    queryFn: () => loadProgress(videoId),
    enabled: viewer.status === 'authenticated',
    staleTime: Infinity,
  })
}

/** Where the player starts: where the viewer stopped, or the start if they saw it to the end. */
export function resumePosition(seconds: number | null | undefined, durationSec: number): number {
  return seconds && seconds < durationSec - END_MARGIN_SEC ? seconds : 0
}
