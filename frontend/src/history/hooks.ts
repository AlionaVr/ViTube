import { useInfiniteQuery } from '@tanstack/react-query'

import { listHistory } from './api'

export const historyKeys = {
  all: ['history'] as const,
  list: ['history', 'list'] as const,
  progress: (videoId: string) => ['history', 'progress', videoId] as const,
}

const firstPage = null as string | null

export function useHistory() {
  return useInfiniteQuery({
    queryKey: historyKeys.list,
    queryFn: ({ pageParam }) => listHistory(pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
  })
}
