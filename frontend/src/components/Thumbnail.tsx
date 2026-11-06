import { formatDuration } from '../lib/format'
import styles from './Thumbnail.module.css'

interface ThumbnailProps {
  src: string
  durationSec: number
  /** Where the viewer stopped; YouTube draws the watched part as a red bar. */
  lastPositionSec?: number | null
  /** Smaller corners for the compact list. */
  compact?: boolean
}

/** 16:9 image with the duration badge. The grey background shows until the image loads. */
export default function Thumbnail({ src, durationSec, lastPositionSec, compact }: ThumbnailProps) {
  const progress = lastPositionSec ? Math.min(lastPositionSec / durationSec, 1) : 0
  return (
    <div className={compact ? `${styles.thumbnail} ${styles.compact}` : styles.thumbnail}>
      <img className={styles.image} src={src} alt="" loading="lazy" decoding="async" />
      {progress > 0 && (
        <div className={styles.progress}>
          <div className={styles.watched} style={{ width: `${progress * 100}%` }} />
        </div>
      )}
      <span className={styles.duration}>{formatDuration(durationSec)}</span>
    </div>
  )
}
