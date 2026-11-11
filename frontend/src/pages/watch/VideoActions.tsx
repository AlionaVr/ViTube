import { useState } from 'react'
import { Link } from 'react-router'

import Avatar from '../../components/Avatar'
import Icon from '../../components/Icon'
import SignInGate from '../../components/SignInGate'
import { formatCompact, formatExact } from '../../lib/format'
import buttons from '../../styles/buttons.module.css'
import { useRateVideo } from '../../videos/hooks'
import { channelUrl } from '../../videos/paths'
import type { Video } from '../../videos/types'
import ShareDialog from './ShareDialog'
import styles from './VideoActions.module.css'

function RatingButtons({ video }: { video: Video }) {
  const rate = useRateVideo(video.id)
  const liked = video.my_rating === 'like'
  const disliked = video.my_rating === 'dislike'

  return (
    <div className={styles.segmented}>
      <SignInGate
        title="Like this video?"
        text="Sign in to make your opinion count."
        onAction={() => rate.mutate(liked ? 'none' : 'like')}
      >
        {(props) => (
          <button
            type="button"
            className={`${styles.segment} ${styles.like}`}
            aria-pressed={liked}
            aria-label={`Like this video along with ${formatExact(video.like_count)} other people`}
            title="I like this"
            {...props}
          >
            <Icon name={liked ? 'likeFill' : 'like'} />
            {video.like_count > 0 && formatCompact(video.like_count)}
          </button>
        )}
      </SignInGate>
      <span className={styles.divider} />
      <SignInGate
        title="Don’t like this video?"
        text="Sign in to make your opinion count."
        onAction={() => rate.mutate(disliked ? 'none' : 'dislike')}
      >
        {(props) => (
          <button
            type="button"
            className={`${styles.segment} ${styles.dislike}`}
            aria-pressed={disliked}
            aria-label="Dislike this video"
            title="I dislike this"
            {...props}
          >
            <Icon name={disliked ? 'dislikeFill' : 'dislike'} />
          </button>
        )}
      </SignInGate>
    </div>
  )
}

/** Channel on the left; like, dislike and Share on the right. */
export default function VideoActions({ video }: { video: Video }) {
  const { channel } = video
  const [sharing, setSharing] = useState(false)

  return (
    <div className={styles.row}>
      <div className={styles.owner}>
        <Link to={channelUrl(channel.handle)} tabIndex={-1} aria-hidden="true">
          <Avatar name={channel.name} src={channel.avatar_url} size={40} />
        </Link>
        <div className={styles.ownerText}>
          <Link to={channelUrl(channel.handle)} className={styles.channelName}>
            {channel.name}
          </Link>
        </div>
      </div>

      <div className={styles.actions}>
        <RatingButtons video={video} />
        <button
          type="button"
          className={`${buttons.pill} ${buttons.tonal} ${buttons.iconLeading}`}
          aria-haspopup="dialog"
          onClick={() => setSharing(true)}
        >
          <Icon name="share" />
          Share
        </button>
        <ShareDialog videoId={video.id} open={sharing} onClose={() => setSharing(false)} />
      </div>
    </div>
  )
}
