import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import { commentKeys } from '../comments/hooks'
import { videoKeys } from '../videos/hooks'
import {
  deleteComment,
  dismissComment,
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

/** A moderator action on a comment; the moderation lists and the video's comments load again. */
function useCommentAction(action: (id: string) => Promise<void>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id }: { id: string; videoId: string }) => action(id),
    onSuccess: (_data, { videoId }) =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: moderationKeys.all }),
        queryClient.invalidateQueries({ queryKey: commentKeys.all(videoId) }),
        queryClient.invalidateQueries({ queryKey: videoKeys.detail(videoId) }),
      ]),
  })
}

export function useDeleteComment() {
  return useCommentAction(deleteComment)
}

export function useDismissComment() {
  return useCommentAction(dismissComment)
}
