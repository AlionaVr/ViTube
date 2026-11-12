import {
  type InfiniteData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import type { Page } from '../videos/types'
import {
  clearHistory,
  getHistorySettings,
  type HistoryItem,
  listHistory,
  removeFromHistory,
  setHistoryPaused,
} from './api'

export const historyKeys = {
  all: ['history'] as const,
  list: ['history', 'list'] as const,
  progress: (videoId: string) => ['history', 'progress', videoId] as const,
  allProgress: ['history', 'progress'] as const,
  settings: ['history', 'settings'] as const,
}

type Items = InfiniteData<Page<HistoryItem>>

const firstPage = null as string | null

export function useHistory() {
  return useInfiniteQuery({
    queryKey: historyKeys.list,
    queryFn: ({ pageParam }) => listHistory(pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
  })
}

/** The row goes once the server agrees, and every thumbnail of the video loses its bar. */
export function useRemoveFromHistory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: removeFromHistory,
    onSuccess: (_data, videoId) => {
      queryClient.setQueryData<Items>(historyKeys.list, (data) =>
        data
          ? {
              ...data,
              pages: data.pages.map((page) => ({
                ...page,
                items: page.items.filter((item) => item.video.id !== videoId),
              })),
            }
          : data,
      )
      queryClient.setQueryData(historyKeys.progress(videoId), null)
    },
  })
}

export function useClearHistory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: clearHistory,
    onSuccess: () => {
      queryClient.setQueryData<Items>(historyKeys.list, (data) =>
        data ? { pages: [{ items: [], next_cursor: null }], pageParams: [firstPage] } : data,
      )
      queryClient.setQueriesData({ queryKey: historyKeys.allProgress }, null)
    },
  })
}

/** Only for a signed-in viewer. */
export function useHistorySettings(enabled: boolean) {
  return useQuery({ queryKey: historyKeys.settings, queryFn: getHistorySettings, enabled })
}

export function useSetHistoryPaused() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: setHistoryPaused,
    onSuccess: (settings) => queryClient.setQueryData(historyKeys.settings, settings),
  })
}
