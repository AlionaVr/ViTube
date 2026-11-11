import EmptyState from '../components/EmptyState'
import ErrorState from '../components/ErrorState'
import Spinner from '../components/Spinner'
import VideoCard, { VideoCardSkeleton } from '../components/VideoCard'
import { useInfiniteScroll } from '../hooks/useInfiniteScroll'
import { useVideoFeed } from '../videos/hooks'
import styles from './HomePage.module.css'

const SKELETON_CARDS = 12

export default function HomePage() {
  const feed = useVideoFeed()
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => void feed.fetchNextPage(),
    feed.hasNextPage && !feed.isFetchingNextPage && !feed.isFetchNextPageError,
  )

  const videos = feed.data?.pages.flatMap((page) => page.items) ?? []

  return (
    <div className={styles.page}>
      <title>ViTube</title>
      {feed.isPending ? (
        <div className={styles.grid} aria-busy="true" aria-label="Loading videos">
          {Array.from({ length: SKELETON_CARDS }, (_, i) => (
            <VideoCardSkeleton key={i} />
          ))}
        </div>
      ) : !feed.data ? (
        <ErrorState title="Can’t load videos" onRetry={() => void feed.refetch()} />
      ) : videos.length === 0 ? (
        <EmptyState title="No videos yet">Uploaded videos will appear here.</EmptyState>
      ) : (
        <>
          <div className={styles.grid}>
            {videos.map((video) => (
              <VideoCard key={video.id} video={video} />
            ))}
          </div>
          <div ref={sentinel} />
          {feed.isFetchingNextPage && (
            <div className={styles.more}>
              <Spinner label="Loading more videos" />
            </div>
          )}
          {feed.isFetchNextPageError && (
            <ErrorState title="Can’t load more videos" onRetry={() => void feed.fetchNextPage()} />
          )}
        </>
      )}
    </div>
  )
}
