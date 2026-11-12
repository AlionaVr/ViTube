import CompactVideoCard, { CompactVideoCardSkeleton } from '../../components/CompactVideoCard'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Spinner from '../../components/Spinner'
import { useHistory } from '../../history/hooks'
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll'
import grid from '../../styles/grid.module.css'
import { useViewer } from '../../viewer/useViewer'
import SignInToSee from '../feed/SignInToSee'
import styles from './HistoryPage.module.css'

const SKELETON_ROWS = 6

function History() {
  const history = useHistory()
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => void history.fetchNextPage(),
    history.hasNextPage && !history.isFetchingNextPage && !history.isFetchNextPageError,
  )
  const items = history.data?.pages.flatMap((page) => page.items) ?? []

  if (history.isPending) {
    return (
      <div className={styles.list} aria-busy="true" aria-label="Loading history">
        {Array.from({ length: SKELETON_ROWS }, (_, i) => (
          <CompactVideoCardSkeleton key={i} />
        ))}
      </div>
    )
  }
  if (!history.data) {
    return <ErrorState title="Can’t load your history" onRetry={() => void history.refetch()} />
  }
  if (items.length === 0) {
    return <EmptyState title="This list has no videos">Videos you watch appear here.</EmptyState>
  }
  return (
    <>
      <div className={styles.list}>
        {items.map(({ video }) => (
          <CompactVideoCard key={video.id} video={video} />
        ))}
      </div>
      <div ref={sentinel} />
      {history.isFetchingNextPage && (
        <div className={grid.more}>
          <Spinner label="Loading more videos" />
        </div>
      )}
      {history.isFetchNextPageError && (
        <ErrorState title="Can’t load more videos" onRetry={() => void history.fetchNextPage()} />
      )}
    </>
  )
}

/** /feed/history: the videos the viewer watched, last first. */
export default function HistoryPage() {
  const viewer = useViewer()
  return (
    <div className={grid.page}>
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
            <h1 className={styles.title}>Watch history</h1>
            <History />
          </>
        )
      )}
    </div>
  )
}
