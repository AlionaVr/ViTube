import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getVideo, listCategories, listMyVideos, listRelated, listVideos, rateVideo } from './api'
import type { Category, Rating, Video, VideoStatus } from './types'

export const videoKeys = {
  feed: (category: Category | null) => ['videos', 'feed', category] as const,
  categories: ['videos', 'categories'] as const,
  detail: (id: string) => ['videos', 'detail', id] as const,
  details: ['videos', 'detail'] as const,
  related: (id: string) => ['videos', 'related', id] as const,
  mine: ['videos', 'mine'] as const,
}

const firstPage = null as string | null

export function useVideoFeed(category: Category | null) {
  return useInfiniteQuery({
    queryKey: videoKeys.feed(category),
    queryFn: ({ pageParam }) => listVideos(category, pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
  })
}

const POLL_MS = 2000

/** The worker has the video: stored and waiting, or being processed. */
function isProcessing(status: VideoStatus): boolean {
  return status === 'uploaded' || status === 'processing'
}

/** While the worker has the video, ask every 2 s: the page shows it once it's ready. */
export function pollWhileProcessing(query: {
  state: { data?: { status: VideoStatus } }
}): number | false {
  const status = query.state.data?.status
  return status && isProcessing(status) ? POLL_MS : false
}

/** Owners and moderators may open a video that is still processing. */
export function useVideo(id: string) {
  return useQuery({
    queryKey: videoKeys.detail(id),
    queryFn: () => getVideo(id),
    refetchInterval: pollWhileProcessing,
  })
}

export function useRelatedVideos(id: string) {
  return useInfiniteQuery({
    queryKey: videoKeys.related(id),
    queryFn: ({ pageParam }) => listRelated(id, pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
  })
}

/** Studio's list. Only for a signed-in viewer: a guest would get 401. */
export function useMyVideos(enabled: boolean) {
  return useInfiniteQuery({
    queryKey: videoKeys.mine,
    queryFn: ({ pageParam }) => listMyVideos(pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
    enabled,
    // A status changes on screen without a reload while any listed video is with the worker.
    refetchInterval: (query) =>
      query.state.data?.pages.some((page) => page.items.some((video) => isProcessing(video.status)))
        ? POLL_MS
        : false,
  })
}

export function useCategories() {
  return useQuery({ queryKey: videoKeys.categories, queryFn: listCategories })
}

/** The like count after the viewer changes their rating; the server's answer replaces it. */
export function applyRating<T extends { like_count: number; my_rating: Rating }>(
  item: T,
  rating: Rating,
): T {
  const own = (r: Rating) => (r === 'like' ? 1 : 0)
  return {
    ...item,
    like_count: item.like_count - own(item.my_rating) + own(rating),
    my_rating: rating,
  }
}

/** Like/dislike shows at once (optimistic) and rolls back if the request fails. */
export function useRateVideo(id: string) {
  const queryClient = useQueryClient()
  const key = videoKeys.detail(id)
  return useMutation({
    mutationFn: (rating: Rating) => rateVideo(id, rating),
    onMutate: async (rating) => {
      await queryClient.cancelQueries({ queryKey: key })
      const previous = queryClient.getQueryData<Video>(key)
      if (previous) queryClient.setQueryData(key, applyRating(previous, rating))
      return { previous }
    },
    onError: (_error, _rating, context) => {
      if (context?.previous) queryClient.setQueryData(key, context.previous)
    },
    onSuccess: (result) => {
      queryClient.setQueryData<Video>(key, (video) => video && { ...video, ...result })
    },
  })
}
