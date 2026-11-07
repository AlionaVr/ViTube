import CompactVideoCard, { CompactVideoCardSkeleton } from '../../components/CompactVideoCard'
import ErrorState from '../../components/ErrorState'
import Spinner from '../../components/Spinner'
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll'
import { useRelatedVideos } from '../../videos/hooks'
import styles from './UpNext.module.css'

export default function UpNext({ videoId }: { videoId: string }) {
  const related = useRelatedVideos(videoId)
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => void related.fetchNextPage(),
    related.hasNextPage && !related.isFetchingNextPage && !related.isFetchNextPageError,
  )

  if (related.isPending) {
    return (
      <div className={styles.list} aria-busy="true" aria-label="Loading related videos">
        {Array.from({ length: 8 }, (_, i) => (
          <CompactVideoCardSkeleton key={i} />
        ))}
      </div>
    )
  }
  if (!related.data) {
    return <ErrorState title="Can’t load related videos" onRetry={() => void related.refetch()} />
  }

  return (
    <section aria-label="Up next">
      <div className={styles.list}>
        {related.data.pages
          .flatMap((page) => page.items)
          .map((video) => (
            <CompactVideoCard key={video.id} video={video} />
          ))}
      </div>
      <div ref={sentinel} />
      {related.isFetchingNextPage && (
        <div className={styles.more}>
          <Spinner label="Loading more videos" />
        </div>
      )}
    </section>
  )
}
