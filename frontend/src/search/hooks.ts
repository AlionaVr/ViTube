import { useInfiniteQuery } from '@tanstack/react-query'

import { search } from './api'

const firstPage = null as string | null

export function useSearch(query: string) {
  return useInfiniteQuery({
    queryKey: ['search', query] as const,
    queryFn: ({ pageParam }) => search(query, pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
  })
}
