import { keepPreviousData, useInfiniteQuery, useQuery } from '@tanstack/react-query'

import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { search, suggest } from './api'

const firstPage = null as string | null
const TYPING_PAUSE_MS = 150

export function useSearch(query: string) {
  return useInfiniteQuery({
    queryKey: ['search', query] as const,
    queryFn: ({ pageParam }) => search(query, pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
  })
}

/** Suggestions for what is typed, asked for in pauses; the last list stays until the next one. */
export function useSuggestions(typed: string) {
  const words = useDebouncedValue(typed.trim(), TYPING_PAUSE_MS)
  return useQuery({
    queryKey: ['search', 'suggestions', words] as const,
    queryFn: () => suggest(words),
    enabled: words !== '',
    placeholderData: keepPreviousData,
  })
}
