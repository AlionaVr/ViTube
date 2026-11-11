import { useState } from 'react'
import { Link } from 'react-router'

import { useChannel } from '../../channels/hooks'
import SubscribeButton from '../../channels/SubscribeButton'
import Avatar from '../../components/Avatar'
import Icon from '../../components/Icon'
import SignInGate from '../../components/SignInGate'
import { formatCompact, formatExact, formatSubscribers } from '../../lib/format'
import SaveDialog from '../../playlists/SaveDialog'
import buttons from '../../styles/buttons.module.css'
import { useRateVideo } from '../../videos/hooks'
import { channelUrl } from '../../videos/paths'
import type { Video } from '../../videos/types'
import { useViewer } from '../../viewer/useViewer'
import Fireworks from './Fireworks'
import ShareDialog from './ShareDialog'
import styles from './VideoActions.module.css'

function RatingButtons({ video }: { video: Video }) {
  const rate = useRateVideo(video.id)
  const liked = video.my_rating === 'like'
  const disliked = video.my_rating === 'dislike'
  // A like (not taking one back) sets off fireworks; the count is the key, so each one starts afresh.
  const [likes, setLikes] = useState(0)
  const [celebrating, setCelebrating] = useState(false)

  function like() {
    if (!liked) {
      setLikes((count) => count + 1)
      setCelebrating(true)
    }
    rate.mutate(liked ? 'none' : 'like')
  }

  return (
    <div className={styles.segmented}>
      <SignInGate
        title="Like this video?"
        text="Sign in to make your opinion count."
        onAction={like}
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
            <span
              key={likes}
              className={celebrating ? `${styles.icon} ${styles.pop}` : styles.icon}
            >
              <Icon name={liked ? 'likeFill' : 'like'} />
              {celebrating && <Fireworks onDone={() => setCelebrating(false)} />}
            </span>
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
  const [saving, setSaving] = useState(false)
  // The channel page's cache entry: subscribing here or there updates both.
  const owner = useChannel(channel.handle)
  const viewer = useViewer()
  const own = viewer.status === 'authenticated' && viewer.user.handle === channel.handle

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
          {/* A space while loading keeps the row's height. */}
          <span className={styles.subscribers}>
            {owner.data ? formatSubscribers(owner.data.subscriber_count) : '\u00a0'}
          </span>
        </div>
        {owner.data && viewer.status !== 'loading' && !own && (
          <SubscribeButton channel={owner.data} />
        )}
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
        <SignInGate
          title="Want to watch this again later?"
          text="Sign in to add this video to a playlist."
          align="end"
          onAction={() => setSaving(true)}
        >
          {(props) => (
            <button
              type="button"
              className={`${buttons.pill} ${buttons.tonal} ${buttons.iconLeading}`}
              aria-haspopup="dialog"
              {...props}
            >
              <Icon name="playlistAdd" />
              Save
            </button>
          )}
        </SignInGate>
        <SaveDialog videoId={video.id} open={saving} onClose={() => setSaving(false)} />
      </div>
    </div>
  )
}
