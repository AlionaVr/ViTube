import { useRef } from 'react'

import { countView, startView } from './api'

// ADR 0011: playback that makes a view, or the whole video if it is shorter; at least 1 s.
const WATCH_SECONDS = 30
const MIN_WATCH_SECONDS = 1

interface Report {
  videoId: string
  started: Promise<void> | null
  counted: boolean
}

/**
 * Reports playback for the view count: `views/start` when it begins, `views` once enough has played.
 * Each at most once per video on this page. Returns the player's `onPlayed`.
 */
export function useViewReport(videoId: string, durationSec: number): (playedSec: number) => void {
  const report = useRef<Report | null>(null)
  const threshold = Math.max(MIN_WATCH_SECONDS, Math.min(WATCH_SECONDS, durationSec))

  return (playedSec) => {
    if (report.current?.videoId !== videoId) {
      report.current = { videoId, started: null, counted: false }
    }
    const current = report.current
    if (!current.started) {
      current.started = startView(videoId)
      current.started.catch(() => {}) // a lost start only means no view
    }
    if (current.counted || playedSec < threshold) return
    current.counted = true
    // The server times the view from `views/start`, so `views` waits until that got there.
    current.started.then(() => countView(videoId)).catch(() => {})
  }
}
