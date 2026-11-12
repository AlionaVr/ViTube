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
import { useViewReport } from '../../views/useViewReport'
import Comments from './comments/Comments'
import Description from './Description'
import { TWO_COLUMNS } from './layout'
import UpNext from './UpNext'
import VideoActions from './VideoActions'
import styles from './WatchPage.module.css'

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

/** The owner and moderators open a restricted video to review it: say who else can't. */
function RestrictionNotice({ video }: { video: Video }) {
  const [title, text] = video.channel_terminated
    ? [
        'Channel terminated',
        'Only moderators can see this channel’s videos. Likes, comments and views are off until an admin reinstates the channel.',
      ]
    : [
        'Hidden by a moderator',
        'Only the channel owner and moderators can see this video. Likes, comments and views are off until a moderator restores it.',
      ]
  return (
    <div className={styles.notice} role="note">
      <Icon name="shieldPerson" />
      <div>
        <p className={styles.noticeTitle}>{title}</p>
        <p className={styles.noticeText}>{text}</p>
      </div>
    </div>
  )
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
  const reportPlayed = useViewReport(id, video.data?.duration_sec ?? 0)

  const next = related.data?.pages[0]?.items[0]
  const notFound = video.error instanceof ApiError && video.error.status === 404
  const ready = video.data?.status === 'ready'
  // Restricted (ADR 0009): frozen for everyone who can open it.
  const frozen = !!video.data && (video.data.is_hidden || video.data.channel_terminated)

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
                onPlayed={frozen ? undefined : reportPlayed}
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
            {frozen && <RestrictionNotice video={video.data} />}
            <h1 className={styles.title}>{video.data.title}</h1>
            {/* Ratings and comments open once the video is ready, and not while it's restricted. */}
            {ready && <VideoActions video={video.data} frozen={frozen} />}
            <Description video={video.data} />
            {!twoColumns && (
              <div className={styles.upNextInline}>
                <UpNext videoId={id} grid />
              </div>
            )}
            {ready &&
              (frozen ? (
                <p className={styles.commentsOff}>Comments are turned off.</p>
              ) : (
                <Comments video={video.data} />
              ))}
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
