import { useState } from 'react'
import { useOutletContext } from 'react-router'

import { useChannelVideos, useMyChannelVideos } from '../../channels/hooks'
import type { MyChannelVideo, VideoSort } from '../../channels/types'
import ChipBar, { type Chip } from '../../components/ChipBar'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Spinner from '../../components/Spinner'
import VideoCard, { VideoCardSkeleton } from '../../components/VideoCard'
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll'
import buttons from '../../styles/buttons.module.css'
import grid from '../../styles/grid.module.css'
import UploadDialog from '../../upload/UploadDialog'
import type { Page, VideoSummary } from '../../videos/types'
import type { ChannelTab } from './ChannelPage'
import styles from './ChannelVideos.module.css'

const SORTS: Chip<VideoSort>[] = [
  { id: 'latest', label: 'Latest' },
  { id: 'popular', label: 'Popular' },
  { id: 'oldest', label: 'Oldest' },
]
const SKELETON_CARDS = 8

/** The owner's empty tab, as YouTube's: an invitation to upload, not the visitors' "no content". */
function CreateContent() {
  const [uploading, setUploading] = useState(false)
  return (
    <>
      <EmptyState
        title="Create content on any device"
        action={
          <button
            type="button"
            className={`${buttons.pill} ${buttons.primary}`}
            onClick={() => setUploading(true)}
          >
            Upload videos
          </button>
        }
      >
        Videos you upload will appear here.
      </EmptyState>
      {uploading && <UploadDialog onClose={() => setUploading(false)} />}
    </>
  )
}

/** The Videos tab in the order of the chosen chip: public videos, or all of them for the owner. */
export default function ChannelVideos() {
  const { handle, view } = useOutletContext<ChannelTab>()
  const [sort, setSort] = useState<VideoSort>('latest')
  const shared = useChannelVideos(handle, sort, view === 'public')
  const mine = useMyChannelVideos(sort, view === 'own')
  const videos = view === 'own' ? mine : shared
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => void videos.fetchNextPage(),
    videos.hasNextPage && !videos.isFetchingNextPage && !videos.isFetchNextPageError,
  )
  const pages: Page<VideoSummary | MyChannelVideo>[] = videos.data?.pages ?? []
  const items = pages.flatMap((page) => page.items)

  if (videos.isSuccess && items.length === 0) {
    return view === 'own' ? (
      <CreateContent />
    ) : (
      <EmptyState title="This channel doesn’t have any content" />
    )
  }
  return (
    <div className={grid.container}>
      <div className={styles.chips}>
        <ChipBar
          label="Sort videos"
          chips={SORTS}
          selected={sort}
          onSelect={(id) => id && setSort(id)}
        />
      </div>
      {videos.isPending ? (
        <div className={grid.grid} aria-busy="true" aria-label="Loading videos">
          {Array.from({ length: SKELETON_CARDS }, (_, i) => (
            <VideoCardSkeleton key={i} showChannel={false} />
          ))}
        </div>
      ) : !videos.data ? (
        <ErrorState title="Can’t load videos" onRetry={() => void videos.refetch()} />
      ) : (
        <>
          <div className={grid.grid}>
            {items.map((video) => (
              <VideoCard
                key={video.id}
                video={video}
                showChannel={false}
                visibility={'visibility' in video ? video.visibility : undefined}
              />
            ))}
          </div>
          <div ref={sentinel} />
          {videos.isFetchingNextPage && (
            <div className={grid.more}>
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
