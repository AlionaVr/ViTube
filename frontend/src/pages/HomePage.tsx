import { useState } from 'react'

import ChipBar, { type Chip } from '../components/ChipBar'
import EmptyState from '../components/EmptyState'
import ErrorState from '../components/ErrorState'
import Spinner from '../components/Spinner'
import VideoCard, { VideoCardSkeleton } from '../components/VideoCard'
import { useInfiniteScroll } from '../hooks/useInfiniteScroll'
import { CATEGORY_LABELS } from '../videos/categories'
import { useCategories, useVideoFeed } from '../videos/hooks'
import type { Category } from '../videos/types'
import styles from './HomePage.module.css'

const SKELETON_CARDS = 12

export default function HomePage() {
  const [category, setCategory] = useState<Category | null>(null)
  const categories = useCategories()
  const feed = useVideoFeed(category)
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => void feed.fetchNextPage(),
    feed.hasNextPage && !feed.isFetchingNextPage && !feed.isFetchNextPageError,
  )

  // Only categories with videos come back, so a chip never leads to an empty feed.
  const chips: Chip<Category>[] = [
    { id: null, label: 'All' },
    ...(categories.data ?? []).map((id) => ({ id, label: CATEGORY_LABELS[id] })),
  ]
  const videos = feed.data?.pages.flatMap((page) => page.items) ?? []

  function selectCategory(id: Category | null) {
    setCategory(id)
    window.scrollTo({ top: 0 })
  }

  return (
    <div className={styles.page}>
      <title>ViTube</title>
      <div className={styles.chips}>
        {categories.isSuccess && categories.data.length > 0 && (
          <ChipBar label="Categories" chips={chips} selected={category} onSelect={selectCategory} />
        )}
      </div>
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
