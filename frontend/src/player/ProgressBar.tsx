import { type PointerEvent, useRef, useState } from 'react'

import { formatDuration } from '../lib/format'
import styles from './Player.module.css'
import { clamp } from './settings'

interface ProgressBarProps {
  currentTime: number
  duration: number
  buffered: number
  onSeek: (time: number) => void
}

const percent = (part: number, whole: number) => `${whole > 0 ? (part / whole) * 100 : 0}%`

/**
 * YouTube's seek bar: thickens on hover, shows the time under the pointer, seeks while dragged.
 * Arrow keys seek through the player's shortcuts.
 */
export default function ProgressBar({ currentTime, duration, buffered, onSeek }: ProgressBarProps) {
  const bar = useRef<HTMLDivElement>(null)
  const [hoverTime, setHoverTime] = useState<number | null>(null)
  const [dragging, setDragging] = useState(false)

  function timeAt(clientX: number): number {
    const rect = bar.current!.getBoundingClientRect()
    const fraction = rect.width > 0 ? (clientX - rect.left) / rect.width : 0
    return clamp(fraction, 0, 1) * duration
  }

  function handlePointerDown(event: PointerEvent) {
    if (event.button !== 0) return
    event.currentTarget.setPointerCapture?.(event.pointerId)
    setDragging(true)
    onSeek(timeAt(event.clientX))
  }

  function handlePointerMove(event: PointerEvent) {
    const time = timeAt(event.clientX)
    setHoverTime(time)
    if (dragging) onSeek(time)
  }

  function handlePointerUp(event: PointerEvent) {
    event.currentTarget.releasePointerCapture?.(event.pointerId)
    setDragging(false)
  }

  return (
    <div
      ref={bar}
      className={dragging ? `${styles.progress} ${styles.dragging}` : styles.progress}
      role="slider"
      tabIndex={0}
      aria-label="Seek slider"
      aria-valuemin={0}
      aria-valuemax={Math.floor(duration)}
      aria-valuenow={Math.floor(currentTime)}
      aria-valuetext={`${formatDuration(currentTime)} of ${formatDuration(duration)}`}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerLeave={() => setHoverTime(null)}
    >
      <div className={styles.track}>
        <div className={styles.loaded} style={{ width: percent(buffered, duration) }} />
        {hoverTime !== null && (
          <div className={styles.hovered} style={{ width: percent(hoverTime, duration) }} />
        )}
        <div className={styles.played} style={{ width: percent(currentTime, duration) }} />
      </div>
      <div className={styles.scrubber} style={{ left: percent(currentTime, duration) }} />
      {hoverTime !== null && (
        <div className={styles.hoverTime} style={{ left: percent(hoverTime, duration) }}>
          {formatDuration(hoverTime)}
        </div>
      )}
    </div>
  )
}
