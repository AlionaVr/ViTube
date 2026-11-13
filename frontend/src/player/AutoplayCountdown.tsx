import { useEffect, useEffectEvent, useState } from 'react'

import styles from './Player.module.css'

/** The video Autoplay plays next. */
export interface UpNextVideo {
  title: string
  channel: string
  thumbnail: string | null
}

const SECONDS = 5

/** YouTube's end screen with Autoplay on: the next video plays after a countdown, unless cancelled. */
export default function AutoplayCountdown({
  video,
  onPlay,
  onCancel,
}: {
  video: UpNextVideo
  onPlay: () => void
  onCancel: () => void
}) {
  const [left, setLeft] = useState(SECONDS)
  const play = useEffectEvent(onPlay)

  useEffect(() => {
    const timer = window.setInterval(() => setLeft((seconds) => seconds - 1), 1000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (left <= 0) play()
  }, [left])

  return (
    <section className={styles.countdown} aria-label="Autoplay countdown">
      <p className={styles.countdownLabel}>Up next in {Math.max(left, 0)}</p>
      {video.thumbnail && (
        <img className={styles.countdownThumbnail} src={video.thumbnail} alt="" />
      )}
      <p className={styles.countdownTitle}>{video.title}</p>
      <p className={styles.countdownChannel}>{video.channel}</p>
      <div className={styles.countdownActions}>
        <button type="button" className={styles.countdownCancel} onClick={onCancel}>
          Cancel
        </button>
        <button type="button" className={styles.countdownPlay} onClick={onPlay}>
          Play now
        </button>
      </div>
    </section>
  )
}
