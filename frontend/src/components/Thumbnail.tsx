import { formatDuration } from '../lib/format'
import styles from './Thumbnail.module.css'

interface ThumbnailProps {
  src: string
  durationSec: number
  /** Smaller corners for the compact list. */
  compact?: boolean
}

/** 16:9 image with the duration badge. The grey background shows until the image loads. */
export default function Thumbnail({ src, durationSec, compact }: ThumbnailProps) {
  return (
    <div className={compact ? `${styles.thumbnail} ${styles.compact}` : styles.thumbnail}>
      <img className={styles.image} src={src} alt="" loading="lazy" decoding="async" />
      <span className={styles.duration}>{formatDuration(durationSec)}</span>
    </div>
  )
}
