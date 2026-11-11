import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import { commentKeys } from '../comments/hooks'
import { videoKeys } from '../videos/hooks'
import {
  type AuditFilters,
  deleteComment,
  dismissComment,
  dismissVideo,
  hideVideo,
  listAudit,
  listHidden,
  listReports,
  listRestricted,
  report,
  type ReportReason,
  type ReportTarget,
  restoreVideo,
  setStatus,
  type UserStatus,
} from './api'

export const moderationKeys = {
  all: ['moderation'] as const,
  reports: ['moderation', 'reports'] as const,
  hidden: ['moderation', 'hidden'] as const,
  accounts: (status: UserStatus | null) => ['moderation', 'accounts', status] as const,
  audit: (filters: AuditFilters) => ['moderation', 'audit', filters] as const,
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

export function useAuditLog(filters: AuditFilters) {
  return useInfiniteQuery({
    queryKey: moderationKeys.audit(filters),
    queryFn: ({ pageParam }) => listAudit(filters, pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
  })
}

export function useRestrictedAccounts(status: UserStatus | null) {
  return useInfiniteQuery({
    queryKey: moderationKeys.accounts(status),
    queryFn: ({ pageParam }) => listRestricted(status, pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
  })
}

/** A viewer's report; it lands in the moderators' queue. */
export function useReport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      target,
      reason,
      details,
    }: {
      target: ReportTarget
      reason: ReportReason
      details: string
    }) => report(target, reason, details),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: moderationKeys.reports }),
  })
}

/** Ban, terminate or reinstate. Their videos may come and go, so everything loads again. */
export function useSetStatus() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      handle,
      status,
      reason,
    }: {
      handle: string
      status: UserStatus
      reason?: string
    }) => setStatus(handle, status, reason),
    onSuccess: () => queryClient.invalidateQueries(),
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
