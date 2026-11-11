import '@fontsource/roboto/700.css'

import type { ReactNode } from 'react'
import { useNavigate, useSearchParams } from 'react-router'

import { ApiError } from '../../api/client'
import ErrorState from '../../components/ErrorState'
import Icon from '../../components/Icon'
import { useMediaQuery } from '../../hooks/useMediaQuery'
import { useStoredFlag } from '../../hooks/useStoredFlag'
import Player from '../../player/Player'
import { useRelatedVideos, useVideo } from '../../videos/hooks'
import { watchUrl } from '../../videos/paths'
import type { Video } from '../../videos/types'
import Comments from './comments/Comments'
import Description from './Description'
import UpNext from './UpNext'
import VideoActions from './VideoActions'
import styles from './WatchPage.module.css'

/** Up next moves under the description below this width, as on YouTube. */
const TWO_COLUMNS = '(min-width: 1016px)'

/** A message in the player's place when there is nothing to play. */
function PlayerNotice({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className={styles.unavailable} role="alert">
      <Icon name="error" size={48} />
      <p className={styles.unavailableTitle}>{title}</p>
      <p>{children}</p>
    </div>
  )
}

/** Owners and moderators may open a video before it's ready. */
function NotReady({ video }: { video: Video }) {
  if (video.status === 'failed') {
    return <PlayerNotice title="Processing failed">{video.error_message}</PlayerNotice>
  }
  if (video.status === 'uploading') {
    return <PlayerNotice title="Upload not finished">This video has no file yet.</PlayerNotice>
  }
  return <PlayerNotice title="Processing video">It will play here once it’s ready.</PlayerNotice>
}

function InfoSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading video">
      <div className={`${styles.ghost} ${styles.ghostTitle}`} />
      <div className={styles.ghostOwner}>
        <div className={`${styles.ghost} ${styles.ghostAvatar}`} />
        <div className={`${styles.ghost} ${styles.ghostLine}`} />
      </div>
      <div className={`${styles.ghost} ${styles.ghostDescription}`} />
    </div>
  )
}

export default function WatchPage() {
  const [params] = useSearchParams()
  const id = params.get('v') ?? ''
  const navigate = useNavigate()
  const video = useVideo(id)
  const related = useRelatedVideos(id)
  const twoColumns = useMediaQuery(TWO_COLUMNS)
  const [theater, toggleTheater] = useStoredFlag('vitube:theater', false)

  const next = related.data?.pages[0]?.items[0]
  const notFound = video.error instanceof ApiError && video.error.status === 404
  const ready = video.data?.status === 'ready'

  return (
    <div className={theater ? `${styles.watch} ${styles.theater}` : styles.watch}>
      <title>{video.data ? `${video.data.title} - ViTube` : 'ViTube'}</title>

      {/* One place in the tree for the player, so theater mode doesn't restart the video. */}
      <div className={styles.player}>
        <div className={styles.playerBox}>
          {video.data &&
            (video.data.media_url && video.data.thumbnail_url ? (
              <Player
                key={video.data.id}
                src={video.data.media_url}
                poster={video.data.thumbnail_url}
                theater={theater}
                onTheaterToggle={toggleTheater}
                onNext={next && (() => navigate(watchUrl(next.id)))}
              />
            ) : (
              <NotReady video={video.data} />
            ))}
          {notFound && (
            <PlayerNotice title="Video unavailable">
              This video isn’t available anymore.
            </PlayerNotice>
          )}
        </div>
      </div>

      <div className={styles.below}>
        {video.data ? (
          <>
            <h1 className={styles.title}>{video.data.title}</h1>
            {/* Ratings and comments open once the video is ready. */}
            {ready && <VideoActions video={video.data} />}
            <Description video={video.data} />
            {!twoColumns && (
              <div className={styles.upNextInline}>
                <UpNext videoId={id} />
              </div>
            )}
            {ready && <Comments video={video.data} />}
          </>
        ) : video.isPending ? (
          <InfoSkeleton />
        ) : (
          !notFound && (
            <ErrorState title="Can’t load this video" onRetry={() => void video.refetch()} />
          )
        )}
      </div>

      {twoColumns && !notFound && (
        <aside className={styles.secondary}>
          <UpNext videoId={id} />
        </aside>
      )}
    </div>
  )
}
