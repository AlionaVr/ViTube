import {
  type InfiniteData,
  type QueryClient,
  useInfiniteQuery,
  useQuery,
} from '@tanstack/react-query'

import type { Page } from '../videos/types'
import { getLiked, type Liked, type LikedItem, listLiked } from './api'

// A rating refetches everything under `all`: the list, its count and its cover move with it.
export const likedKeys = {
  all: ['liked'] as const,
  summary: ['liked', 'summary'] as const,
  items: ['liked', 'items'] as const,
}

/** Only for a signed-in viewer: a guest has none. */
export function useLiked(enabled: boolean) {
  return useQuery({ queryKey: likedKeys.summary, queryFn: getLiked, enabled })
}

export function useLikedItems(enabled: boolean) {
  return useInfiniteQuery({
    queryKey: likedKeys.items,
    queryFn: ({ pageParam }) => listLiked(pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
    enabled,
  })
}

/** Takes a video off the cached list and count at once, as YouTube does. The refetch after the
 *  rating confirms it, or brings the row back if the rating failed. */
export async function dropLiked(queryClient: QueryClient, videoId: string): Promise<void> {
  await queryClient.cancelQueries({ queryKey: likedKeys.all })
  queryClient.setQueryData<InfiniteData<Page<LikedItem>>>(
    likedKeys.items,
    (data) =>
      data && {
        ...data,
        pages: data.pages.map((page) => ({
          ...page,
          items: page.items.filter((item) => item.video.id !== videoId),
        })),
      },
  )
  queryClient.setQueryData<Liked>(
    likedKeys.summary,
    (liked) => liked && { ...liked, video_count: Math.max(0, liked.video_count - 1) },
  )
}
