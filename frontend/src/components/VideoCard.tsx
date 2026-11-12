import { Link } from 'react-router'

import { formatTimeAgo, formatViews } from '../lib/format'
import { channelUrl, watchUrl } from '../videos/paths'
import type { Visibility, VideoSummary } from '../videos/types'
import Avatar from './Avatar'
import Thumbnail from './Thumbnail'
import styles from './VideoCard.module.css'
import VisibilityBadge from './VisibilityBadge'

interface VideoCardProps {
  video: VideoSummary
  /** Off on a channel's own page, where every card is that channel's. */
  showChannel?: boolean
  /** On the owner's own channel, which lists every visibility: marks what isn't public. */
  visibility?: Visibility
  /** A shelf's narrow card (the You page): no avatar, smaller type. */
  compact?: boolean
}

/** A card in a video grid. The title link is the one tab stop to the video. */
export default function VideoCard({
  video,
  showChannel = true,
  visibility,
  compact,
}: VideoCardProps) {
  const { channel } = video
  return (
    <article className={compact ? `${styles.card} ${styles.compact}` : styles.card}>
      <Link to={watchUrl(video.id)} tabIndex={-1} aria-hidden="true">
        <Thumbnail src={video.thumbnail_url} durationSec={video.duration_sec} videoId={video.id} />
      </Link>
      <div className={styles.details}>
        {showChannel && !compact && (
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
          {visibility && <VisibilityBadge visibility={visibility} />}
        </div>
      </div>
    </article>
  )
}

/** Same geometry as the card, so nothing jumps when data arrives. */
export function VideoCardSkeleton({
  showChannel = true,
  compact,
}: {
  showChannel?: boolean
  compact?: boolean
}) {
  return (
    <div className={compact ? `${styles.card} ${styles.compact}` : styles.card} aria-hidden="true">
      <div className={styles.ghostThumbnail} />
      <div className={styles.details}>
        {showChannel && !compact && <div className={styles.ghostAvatar} />}
        <div className={styles.meta}>
          <div className={styles.ghostLine} />
          <div className={`${styles.ghostLine} ${styles.ghostShort}`} />
        </div>
      </div>
    </div>
  )
}
