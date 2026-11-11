import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Spinner from '../../components/Spinner'
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll'
import type { ModeratedVideo } from '../../moderation/api'
import { useHiddenVideos, useRestoreVideo } from '../../moderation/hooks'
import buttons from '../../styles/buttons.module.css'
import styles from './ModerationPage.module.css'
import { useModerator } from './useModerator'
import VideoCell, { OwnNote } from './VideoCell'

/** Videos moderators hid, newest first: where a hide is undone. */
export default function HiddenVideos() {
  const hidden = useHiddenVideos()
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => hidden.fetchNextPage(),
    hidden.hasNextPage && !hidden.isFetchingNextPage,
  )

  if (hidden.isPending) {
    return (
      <div className={styles.loading}>
        <Spinner />
      </div>
    )
  }
  if (hidden.isError) {
    return <ErrorState title="Couldn't load hidden videos" onRetry={() => hidden.refetch()} />
  }
  const videos = hidden.data.pages.flatMap((page) => page.items)
  if (videos.length === 0) {
    return (
      <EmptyState title="No hidden videos">
        Videos you hide show up here, so you can restore them.
      </EmptyState>
    )
  }

  return (
    <>
      <ol className={styles.rows} aria-label="Hidden videos">
        {videos.map((video) => (
          <HiddenRow key={video.id} video={video} />
        ))}
      </ol>
      <div ref={sentinel} />
      {hidden.isFetchingNextPage && (
        <div className={styles.loading}>
          <Spinner />
        </div>
      )}
    </>
  )
}

function HiddenRow({ video }: { video: ModeratedVideo }) {
  const own = video.channel.handle === useModerator().handle
  const restore = useRestoreVideo()
  return (
    <li className={styles.row}>
      <VideoCell video={video} />
      <div className={styles.actions}>
        {own ? (
          <OwnNote what="video" />
        ) : (
          <button
            type="button"
            className={`${buttons.pill} ${buttons.tonal} ${buttons.small}`}
            aria-label={`Restore “${video.title}”`}
            disabled={restore.isPending}
            onClick={() => restore.mutate({ id: video.id })}
          >
            Restore
          </button>
        )}
        {restore.isError && (
          <p className={styles.error} role="alert">
            {restore.error.message}
          </p>
        )}
      </div>
    </li>
  )
}
