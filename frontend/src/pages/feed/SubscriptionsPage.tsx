import { Link } from 'react-router'

import { useSubscriptionsFeed } from '../../channels/hooks'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Spinner from '../../components/Spinner'
import VideoCard, { VideoCardSkeleton } from '../../components/VideoCard'
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll'
import buttons from '../../styles/buttons.module.css'
import { useViewer } from '../../viewer/useViewer'
// The same grid as Home.
import grid from '../HomePage.module.css'
import SignInToSee from './SignInToSee'
import styles from './SubscriptionsPage.module.css'

const SKELETON_CARDS = 12

function Feed() {
  const feed = useSubscriptionsFeed()
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => void feed.fetchNextPage(),
    feed.hasNextPage && !feed.isFetchingNextPage && !feed.isFetchNextPageError,
  )
  const videos = feed.data?.pages.flatMap((page) => page.items) ?? []

  if (feed.isPending) {
    return (
      <div className={grid.grid} aria-busy="true" aria-label="Loading videos">
        {Array.from({ length: SKELETON_CARDS }, (_, i) => (
          <VideoCardSkeleton key={i} />
        ))}
      </div>
    )
  }
  if (!feed.data) {
    return <ErrorState title="Can’t load videos" onRetry={() => void feed.refetch()} />
  }
  if (videos.length === 0) {
    return (
      <EmptyState title="No new videos">
        New videos from the channels you subscribe to appear here.
      </EmptyState>
    )
  }
  return (
    <>
      <div className={grid.grid}>
        {videos.map((video) => (
          <VideoCard key={video.id} video={video} />
        ))}
      </div>
      <div ref={sentinel} />
      {feed.isFetchingNextPage && (
        <div className={grid.more}>
          <Spinner label="Loading more videos" />
        </div>
      )}
      {feed.isFetchNextPageError && (
        <ErrorState title="Can’t load more videos" onRetry={() => void feed.fetchNextPage()} />
      )}
    </>
  )
}

/** /feed/subscriptions: the newest public videos of the viewer's subscriptions. */
export default function SubscriptionsPage() {
  const viewer = useViewer()
  return (
    <div className={grid.page}>
      <title>Subscriptions - ViTube</title>
      {viewer.status === 'guest' ? (
        <SignInToSee
          icon="subscriptions"
          title="Don’t miss new videos"
          text="Sign in to see updates from your favorite ViTube channels"
        />
      ) : (
        viewer.status === 'authenticated' && (
          <>
            <div className={styles.header}>
              <h1 className={styles.title}>Latest</h1>
              <Link to="/feed/channels" className={`${buttons.pill} ${buttons.link}`}>
                Manage
              </Link>
            </div>
            <Feed />
          </>
        )
      )}
    </div>
  )
}
