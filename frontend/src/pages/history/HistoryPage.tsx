import { useState } from 'react'
import { Link } from 'react-router'

import Dialog from '../../components/Dialog'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Icon from '../../components/Icon'
import IconButton from '../../components/IconButton'
import Spinner from '../../components/Spinner'
import Thumbnail from '../../components/Thumbnail'
import type { HistoryItem } from '../../history/api'
import { useClearHistory, useHistory, useRemoveFromHistory } from '../../history/hooks'
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll'
import { useToast } from '../../hooks/useToast'
import { formatHistoryDay, formatViews } from '../../lib/format'
import buttons from '../../styles/buttons.module.css'
import { channelUrl, watchUrl } from '../../videos/paths'
import { useViewer } from '../../viewer/useViewer'
import SignInToSee from '../feed/SignInToSee'
import styles from './HistoryPage.module.css'

const SKELETON_ROWS = 4

interface Day {
  label: string
  items: HistoryItem[]
}

/** Last watched first, so each day's videos are next to each other. */
function byDay(items: HistoryItem[]): Day[] {
  const days: Day[] = []
  for (const item of items) {
    const label = formatHistoryDay(item.watched_at)
    if (days.at(-1)?.label === label) days.at(-1)!.items.push(item)
    else days.push({ label, items: [item] })
  }
  return days
}

/** A search result row with the remove button, as on YouTube. The title is the one tab stop. */
function Row({ item, onRemove }: { item: HistoryItem; onRemove: () => void }) {
  const { video } = item
  return (
    <article className={styles.row}>
      <Link to={watchUrl(video.id)} className={styles.thumbnail} tabIndex={-1} aria-hidden="true">
        <Thumbnail src={video.thumbnail_url} durationSec={video.duration_sec} videoId={video.id} />
      </Link>
      <div className={styles.details}>
        <h3 className={styles.title}>
          <Link to={watchUrl(video.id)} title={video.title}>
            {video.title}
          </Link>
        </h3>
        <p className={styles.line}>
          <Link to={channelUrl(video.channel.handle)} className={styles.channel}>
            {video.channel.name}
          </Link>{' '}
          • {formatViews(video.view_count)}
        </p>
        {video.description && <p className={styles.description}>{video.description}</p>}
      </div>
      <IconButton icon="close" label="Remove from watch history" onClick={onRemove} />
    </article>
  )
}

function RowSkeleton() {
  return (
    <div className={styles.row} aria-hidden="true">
      <div className={`${styles.thumbnail} ${styles.ghostThumbnail}`} />
      <div className={styles.details}>
        <div className={styles.ghostLine} />
        <div className={`${styles.ghostLine} ${styles.ghostShort}`} />
      </div>
    </div>
  )
}

function History() {
  const history = useHistory()
  const remove = useRemoveFromHistory()
  const toast = useToast()
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => void history.fetchNextPage(),
    history.hasNextPage && !history.isFetchingNextPage && !history.isFetchNextPageError,
  )

  if (history.isPending) {
    return (
      <div className={styles.day} aria-busy="true" aria-label="Loading history">
        {Array.from({ length: SKELETON_ROWS }, (_, i) => (
          <RowSkeleton key={i} />
        ))}
      </div>
    )
  }
  if (!history.data) {
    return <ErrorState title="Can’t load your history" onRetry={() => void history.refetch()} />
  }
  const items = history.data.pages.flatMap((page) => page.items)
  if (items.length === 0) {
    return <EmptyState title="This list has no videos">Videos you watch appear here.</EmptyState>
  }

  // A promise, not a mutate callback: those skip all but the last call, and the row unmounts.
  const removeVideo = (videoId: string) =>
    void remove.mutateAsync(videoId).then(
      () => toast('Removed from watch history'),
      () => toast('Couldn’t remove the video. Try again.'),
    )

  return (
    <>
      {byDay(items).map((day) => (
        <section key={day.label} className={styles.day} aria-label={day.label}>
          <h2 className={styles.dayTitle}>{day.label}</h2>
          {day.items.map((item) => (
            <Row key={item.video.id} item={item} onRemove={() => removeVideo(item.video.id)} />
          ))}
        </section>
      ))}
      <div ref={sentinel} />
      {history.isFetchingNextPage && (
        <div className={styles.more}>
          <Spinner label="Loading more videos" />
        </div>
      )}
      {history.isFetchNextPageError && (
        <ErrorState title="Can’t load more videos" onRetry={() => void history.fetchNextPage()} />
      )}
    </>
  )
}

function ClearHistory() {
  const [confirming, setConfirming] = useState(false)
  const clear = useClearHistory()
  const toast = useToast()

  function confirm() {
    setConfirming(false)
    clear.mutateAsync().then(
      () => toast('Watch history cleared'),
      () => toast('Couldn’t clear watch history. Try again.'),
    )
  }

  return (
    <>
      <button
        type="button"
        className={`${buttons.pill} ${buttons.text} ${buttons.iconLeading} ${styles.action}`}
        onClick={() => setConfirming(true)}
      >
        <Icon name="delete" />
        Clear all watch history
      </button>
      <Dialog open={confirming} onClose={() => setConfirming(false)} label="Clear watch history?">
        <h2 className={styles.confirmTitle}>Clear watch history?</h2>
        <p className={styles.confirmText}>
          Your ViTube watch history will be cleared on all devices, and videos will play from the
          start again.
        </p>
        <div className={styles.confirmActions}>
          <button
            type="button"
            className={`${buttons.pill} ${buttons.text}`}
            onClick={() => setConfirming(false)}
          >
            Cancel
          </button>
          <button type="button" className={`${buttons.pill} ${buttons.link}`} onClick={confirm}>
            Clear watch history
          </button>
        </div>
      </Dialog>
    </>
  )
}

/** /feed/history: the videos the viewer watched, by day, last first. */
export default function HistoryPage() {
  const viewer = useViewer()
  return (
    <div className={styles.page}>
      <title>Watch history - ViTube</title>
      {viewer.status === 'guest' ? (
        <SignInToSee
          icon="history"
          title="Keep track of what you watch"
          text="Watch history isn’t viewable when signed out."
        />
      ) : (
        viewer.status === 'authenticated' && (
          <>
            <h1 className={styles.heading}>Watch history</h1>
            <div className={styles.columns}>
              <div className={styles.main}>
                <History />
              </div>
              <div className={styles.side}>
                <ClearHistory />
              </div>
            </div>
          </>
        )
      )}
    </div>
  )
}
