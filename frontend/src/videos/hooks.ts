import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getVideo, listCategories, listRelated, listVideos, rateVideo } from './api'
import type { Category, Rating, Video } from './types'

export const videoKeys = {
  feed: (category: Category | null) => ['videos', 'feed', category] as const,
  categories: ['videos', 'categories'] as const,
  detail: (id: string) => ['videos', 'detail', id] as const,
  details: ['videos', 'detail'] as const,
  related: (id: string) => ['videos', 'related', id] as const,
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

export function useVideo(id: string) {
  return useQuery({ queryKey: videoKeys.detail(id), queryFn: () => getVideo(id) })
}

export function useRelatedVideos(id: string) {
  return useInfiniteQuery({
    queryKey: videoKeys.related(id),
    queryFn: ({ pageParam }) => listRelated(id, pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
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
