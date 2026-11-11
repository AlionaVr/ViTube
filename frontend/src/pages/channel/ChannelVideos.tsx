import { useState } from 'react'
import { useOutletContext } from 'react-router'

import { useChannelVideos } from '../../channels/hooks'
import type { VideoSort } from '../../channels/types'
import ChipBar, { type Chip } from '../../components/ChipBar'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Spinner from '../../components/Spinner'
import VideoCard, { VideoCardSkeleton } from '../../components/VideoCard'
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll'
import styles from './ChannelVideos.module.css'

const SORTS: Chip<VideoSort>[] = [
  { id: 'latest', label: 'Latest' },
  { id: 'popular', label: 'Popular' },
  { id: 'oldest', label: 'Oldest' },
]
const SKELETON_CARDS = 8

/** The Videos tab: the channel's public videos, in the order of the chosen chip. */
export default function ChannelVideos() {
  const handle = useOutletContext<string>()
  const [sort, setSort] = useState<VideoSort>('latest')
  const videos = useChannelVideos(handle, sort)
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => void videos.fetchNextPage(),
    videos.hasNextPage && !videos.isFetchingNextPage && !videos.isFetchNextPageError,
  )
  const items = videos.data?.pages.flatMap((page) => page.items) ?? []

  if (videos.isSuccess && items.length === 0) {
    return <EmptyState title="This channel doesn’t have any content" />
  }
  return (
    <div className={styles.tab}>
      <div className={styles.chips}>
        <ChipBar
          label="Sort videos"
          chips={SORTS}
          selected={sort}
          onSelect={(id) => id && setSort(id)}
        />
      </div>
      {videos.isPending ? (
        <div className={styles.grid} aria-busy="true" aria-label="Loading videos">
          {Array.from({ length: SKELETON_CARDS }, (_, i) => (
            <VideoCardSkeleton key={i} showChannel={false} />
          ))}
        </div>
      ) : !videos.data ? (
        <ErrorState title="Can’t load videos" onRetry={() => void videos.refetch()} />
      ) : (
        <>
          <div className={styles.grid}>
            {items.map((video) => (
              <VideoCard key={video.id} video={video} showChannel={false} />
            ))}
          </div>
          <div ref={sentinel} />
          {videos.isFetchingNextPage && (
            <div className={styles.more}>
              <Spinner label="Loading more videos" />
            </div>
          )}
          {videos.isFetchNextPageError && (
            <ErrorState
              title="Can’t load more videos"
              onRetry={() => void videos.fetchNextPage()}
            />
          )}
        </>
      )}
    </div>
  )
}
