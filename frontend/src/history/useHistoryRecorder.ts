import { type QueryClient, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import { savePosition } from './api'
import { historyKeys } from './hooks'

/** While playing, a save at most this often; start, pause and end save at once. */
const SAVE_EVERY_MS = 10_000

interface Watch {
  videoId: string
  latest: number | null
  sent: number | null
  sentAt: number
}

function save(watch: Watch, keepalive: boolean, queryClient: QueryClient) {
  const { videoId, latest } = watch
  if (latest === null || latest === watch.sent) return
  watch.sent = latest
  watch.sentAt = Date.now()
  savePosition(videoId, latest, keepalive).then(
    // The thumbnails' progress bars move with it, without a refetch.
    () => queryClient.setQueryData(historyKeys.progress(videoId), latest),
    () => {}, // a lost save is retried by the next one
  )
}

/**
 * Saves where playback is to the viewer's history. The last position goes out when the viewer
 * leaves the video: another video, another page, or a closing tab. Returns the player's `onPosition`.
 */
export function useHistoryRecorder(
  videoId: string,
  enabled: boolean,
): (seconds: number, urgent: boolean) => void {
  const watch = useRef<Watch | null>(null)
  const queryClient = useQueryClient()

  useEffect(() => {
    const flush = () => {
      if (watch.current) save(watch.current, true, queryClient)
    }
    window.addEventListener('pagehide', flush)
    return () => {
      window.removeEventListener('pagehide', flush)
      flush() // the video this effect was for
    }
  }, [videoId, queryClient])

  return (seconds, urgent) => {
    if (!enabled || !Number.isFinite(seconds)) return
    if (watch.current?.videoId !== videoId) {
      watch.current = { videoId, latest: null, sent: null, sentAt: 0 }
    }
    const current = watch.current
    current.latest = Math.floor(seconds)
    if (urgent || Date.now() - current.sentAt >= SAVE_EVERY_MS) save(current, false, queryClient)
  }
}
