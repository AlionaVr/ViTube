import { Link } from 'react-router'

import { formatTimeAgo, formatViews } from '../lib/format'
import { channelUrl, watchUrl } from '../videos/paths'
import type { VideoSummary } from '../videos/types'
import Avatar from './Avatar'
import Thumbnail from './Thumbnail'
import styles from './VideoCard.module.css'

interface VideoCardProps {
  video: VideoSummary
  /** Off on a channel's own page, where every card is that channel's. */
  showChannel?: boolean
}

/** A card in a video grid. The title link is the one tab stop to the video. */
export default function VideoCard({ video, showChannel = true }: VideoCardProps) {
  const { channel } = video
  return (
    <article className={styles.card}>
      <Link to={watchUrl(video.id)} tabIndex={-1} aria-hidden="true">
        <Thumbnail src={video.thumbnail_url} durationSec={video.duration_sec} />
      </Link>
      <div className={styles.details}>
        {showChannel && (
          <Link to={channelUrl(channel.handle)} tabIndex={-1} aria-hidden="true">
            <Avatar name={channel.name} src={channel.avatar_url} size={36} />
          </Link>
        )}
        <div className={styles.meta}>
          <h3 className={styles.title}>
            <Link to={watchUrl(video.id)} title={video.title}>
              {video.title}
            </Link>
          </h3>
          {showChannel && (
            <Link to={channelUrl(channel.handle)} className={styles.channel}>
              {channel.name}
            </Link>
          )}
          <p className={styles.stats}>
            {formatViews(video.view_count)} • {formatTimeAgo(video.created_at)}
          </p>
        </div>
      </div>
    </article>
  )
}

/** Same geometry as the card, so nothing jumps when data arrives. */
export function VideoCardSkeleton({ showChannel = true }: { showChannel?: boolean }) {
  return (
    <div className={styles.card} aria-hidden="true">
      <div className={styles.ghostThumbnail} />
      <div className={styles.details}>
        {showChannel && <div className={styles.ghostAvatar} />}
        <div className={styles.meta}>
          <div className={styles.ghostLine} />
          <div className={`${styles.ghostLine} ${styles.ghostShort}`} />
        </div>
      </div>
    </div>
  )
}
