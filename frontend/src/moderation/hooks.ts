import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import { videoKeys } from '../videos/hooks'
import {
  dismissVideo,
  hideVideo,
  listHidden,
  listReports,
  type ReportReason,
  restoreVideo,
} from './api'

export const moderationKeys = {
  all: ['moderation'] as const,
  reports: ['moderation', 'reports'] as const,
  hidden: ['moderation', 'hidden'] as const,
}

const firstPage = null as string | null

export function useReportQueue() {
  return useInfiniteQuery({
    queryKey: moderationKeys.reports,
    queryFn: ({ pageParam }) => listReports(pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
  })
}

export function useHiddenVideos() {
  return useInfiniteQuery({
    queryKey: moderationKeys.hidden,
    queryFn: ({ pageParam }) => listHidden(pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
  })
}

/** A moderator action on a video; the moderation lists and the video's own page load again. */
function useVideoAction<V extends { id: string }>(action: (variables: V) => Promise<void>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: action,
    onSuccess: (_data, { id }) =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: moderationKeys.all }),
        queryClient.invalidateQueries({ queryKey: videoKeys.detail(id) }),
      ]),
  })
}

export function useHideVideo() {
  return useVideoAction(({ id, reason }: { id: string; reason: ReportReason }) =>
    hideVideo(id, reason),
  )
}

export function useRestoreVideo() {
  return useVideoAction(({ id }: { id: string }) => restoreVideo(id))
}

export function useDismissVideo() {
  return useVideoAction(({ id }: { id: string }) => dismissVideo(id))
}
