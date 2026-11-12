import { Link } from 'react-router'

import Avatar from '../../components/Avatar'
import Thumbnail from '../../components/Thumbnail'
import { formatTimeAgo } from '../../lib/format'
import type { ModeratedComment } from '../../moderation/api'
import { channelUrl, watchUrl } from '../../videos/paths'
import styles from './ModerationPage.module.css'

/** A reported comment, like YouTube Studio's comments: who wrote what, on which video. */
export default function CommentCell({ comment }: { comment: ModeratedComment }) {
  const { video, author } = comment
  return (
    <>
      <Link to={watchUrl(video.id)} className={styles.thumb} tabIndex={-1} aria-hidden>
        {video.thumbnail_url && video.duration_sec !== null ? (
          <Thumbnail src={video.thumbnail_url} durationSec={video.duration_sec} compact />
        ) : (
          <div className={styles.noThumb} />
        )}
      </Link>
      <div className={styles.video}>
        <p className={styles.commentHead}>
          <Avatar name={author.handle} src={author.avatar_url} size={24} />
          <Link to={channelUrl(author.handle)} className={styles.author}>
            @{author.handle}
          </Link>
          <span className={styles.meta}>{formatTimeAgo(comment.published_at)}</span>
          {comment.is_deleted && <span className={styles.hiddenBadge}>Deleted</span>}
        </p>
        <p className={styles.commentText}>{comment.text}</p>
        <p className={styles.meta}>
          {comment.is_reply ? 'Reply on ' : 'Comment on '}
          <Link to={watchUrl(video.id)} className={styles.inlineLink}>
            {video.title}
          </Link>
        </p>
      </div>
    </>
  )
}
