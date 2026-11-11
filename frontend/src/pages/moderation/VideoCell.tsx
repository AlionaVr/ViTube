import { Link } from 'react-router'

import Thumbnail from '../../components/Thumbnail'
import type { ModeratedVideo } from '../../moderation/api'
import { channelUrl, watchUrl } from '../../videos/paths'
import styles from './ModerationPage.module.css'

const VISIBILITY: Record<ModeratedVideo['visibility'], string> = {
  public: 'Public',
  unlisted: 'Unlisted',
  private: 'Private',
}

/** Thumbnail, title, channel and visibility: the start of every row. */
export default function VideoCell({ video }: { video: ModeratedVideo }) {
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
        <Link to={watchUrl(video.id)} className={styles.videoTitle}>
          {video.title}
        </Link>
        <Link to={channelUrl(video.channel.handle)} className={styles.meta}>
          {video.channel.name}
        </Link>
        <p className={styles.meta}>
          {VISIBILITY[video.visibility]}
          {video.is_hidden && <span className={styles.hiddenBadge}>Hidden</span>}
        </p>
      </div>
    </>
  )
}

/** Moderators don't decide about their own videos or comments; the API refuses it too. */
export function OwnNote({ what }: { what: 'video' | 'comment' }) {
  return <p className={styles.ownNote}>Your {what}: another moderator decides</p>
}
