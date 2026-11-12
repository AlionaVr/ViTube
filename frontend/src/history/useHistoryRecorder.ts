import { useEffect, useRef } from 'react'

import { savePosition } from './api'

/** While playing, a save at most this often; start, pause and end save at once. */
const SAVE_EVERY_MS = 10_000

interface Watch {
  videoId: string
  latest: number | null
  sent: number | null
  sentAt: number
}

function save(watch: Watch, keepalive: boolean) {
  if (watch.latest === null || watch.latest === watch.sent) return
  watch.sent = watch.latest
  watch.sentAt = Date.now()
  savePosition(watch.videoId, watch.latest, keepalive).catch(() => {}) // a lost save is retried by the next one
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

  useEffect(() => {
    const flush = () => {
      if (watch.current) save(watch.current, true)
    }
    window.addEventListener('pagehide', flush)
    return () => {
      window.removeEventListener('pagehide', flush)
      flush() // the video this effect was for
    }
  }, [videoId])

  return (seconds, urgent) => {
    if (!enabled || !Number.isFinite(seconds)) return
    if (watch.current?.videoId !== videoId) {
      watch.current = { videoId, latest: null, sent: null, sentAt: 0 }
    }
    const current = watch.current
    current.latest = Math.floor(seconds)
    if (urgent || Date.now() - current.sentAt >= SAVE_EVERY_MS) save(current, false)
  }
}
