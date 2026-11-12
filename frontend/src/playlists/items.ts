import type { InfiniteData, UseInfiniteQueryResult } from '@tanstack/react-query'

import type { Page, VideoSummary } from '../videos/types'

/** A playlist's or Liked videos' pages of rows. */
export type ItemsQuery = Pick<
  UseInfiniteQueryResult<InfiniteData<Page<{ video: VideoSummary }>>>,
  | 'data'
  | 'isPending'
  | 'refetch'
  | 'fetchNextPage'
  | 'hasNextPage'
  | 'isFetchingNextPage'
  | 'isFetchNextPageError'
>

export function videosOf(query: ItemsQuery): VideoSummary[] {
  return query.data?.pages.flatMap((page) => page.items.map((item) => item.video)) ?? []
}
