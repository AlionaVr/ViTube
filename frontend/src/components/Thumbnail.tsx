import { useWatchProgress } from '../history/progress'
import { formatDuration } from '../lib/format'
import styles from './Thumbnail.module.css'

interface ThumbnailProps {
  src: string
  durationSec: number
  /** Smaller corners for the compact list. */
  compact?: boolean
  /** Shows how much of it the viewer watched. */
  videoId?: string
}

/** YouTube's red bar along the bottom: where the viewer stopped. */
function WatchedBar({ videoId, durationSec }: { videoId: string; durationSec: number }) {
  const { data: seconds } = useWatchProgress(videoId)
  if (!seconds) return null
  const percent = durationSec > 0 ? Math.min(100, Math.round((seconds / durationSec) * 100)) : 100
  return (
    <div
      className={styles.progress}
      role="progressbar"
      aria-label="Watched"
      aria-valuenow={percent}
      aria-valuetext={`${percent}% watched`}
    >
      <div className={styles.watched} style={{ width: `${percent}%` }} />
    </div>
  )
}

/** 16:9 image with the duration badge. The grey background shows until the image loads. */
export default function Thumbnail({ src, durationSec, compact, videoId }: ThumbnailProps) {
  return (
    <div className={compact ? `${styles.thumbnail} ${styles.compact}` : styles.thumbnail}>
      <img className={styles.image} src={src} alt="" loading="lazy" decoding="async" />
      <span className={styles.duration}>{formatDuration(durationSec)}</span>
      {videoId && <WatchedBar videoId={videoId} durationSec={durationSec} />}
    </div>
  )
}
