import { useInfiniteQuery, useQuery } from '@tanstack/react-query'

import { getLiked, listLiked } from './api'

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
