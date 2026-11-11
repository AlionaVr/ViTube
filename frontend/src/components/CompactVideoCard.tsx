import { Link } from 'react-router'

import { formatTimeAgo, formatViews } from '../lib/format'
import { watchUrl } from '../videos/paths'
import type { VideoSummary } from '../videos/types'
import styles from './CompactVideoCard.module.css'
import Thumbnail from './Thumbnail'

/** A row in "Up next": the whole row is one link, as on YouTube. */
export default function CompactVideoCard({ video }: { video: VideoSummary }) {
  return (
    <Link to={watchUrl(video.id)} className={styles.card}>
      <div className={styles.thumbnail}>
        <Thumbnail src={video.thumbnail_url} durationSec={video.duration_sec} compact />
      </div>
      <div className={styles.meta}>
        <h3 className={styles.title} title={video.title}>
          {video.title}
        </h3>
        <p className={styles.line}>{video.channel.name}</p>
        <p className={styles.line}>
          {formatViews(video.view_count)} • {formatTimeAgo(video.created_at)}
        </p>
      </div>
    </Link>
  )
}

export function CompactVideoCardSkeleton() {
  return (
    <div className={styles.card} aria-hidden="true">
      <div className={`${styles.thumbnail} ${styles.ghost}`} />
      <div className={styles.meta}>
        <div className={styles.ghostLine} />
        <div className={`${styles.ghostLine} ${styles.ghostShort}`} />
      </div>
    </div>
  )
}
