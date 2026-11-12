import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import { commentKeys } from '../comments/hooks'
import { useToast } from '../hooks/useToast'
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

const STATUS_SET: Record<UserStatus, (handle: string) => string> = {
  active: (handle) => `@${handle} reinstated`,
  banned: (handle) => `@${handle} banned`,
  terminated: (handle) => `@${handle}’s channel terminated`,
}

/** Ban, terminate or reinstate. Their videos may come and go, so everything loads again. */
export function useSetStatus() {
  const queryClient = useQueryClient()
  const toast = useToast()
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
    onSuccess: (_data, { handle, status }) => {
      toast(STATUS_SET[status](handle))
      return queryClient.invalidateQueries()
    },
  })
}

/** A moderator action on a video: a toast says what it did; the moderation lists and the video's
 * own page load again. */
function useVideoAction<V extends { id: string }>(
  action: (variables: V) => Promise<void>,
  done: string,
) {
  const queryClient = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: action,
    onSuccess: (_data, { id }) => {
      toast(done)
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: moderationKeys.all }),
        queryClient.invalidateQueries({ queryKey: videoKeys.detail(id) }),
      ])
    },
  })
}

export function useHideVideo() {
  return useVideoAction(
    ({ id, reason }: { id: string; reason: ReportReason }) => hideVideo(id, reason),
    'Video hidden',
  )
}

export function useRestoreVideo() {
  return useVideoAction(({ id }: { id: string }) => restoreVideo(id), 'Video restored')
}

export function useDismissVideo() {
  return useVideoAction(({ id }: { id: string }) => dismissVideo(id), 'Reports dismissed')
}

/** A moderator action on a comment: a toast says what it did; the moderation lists and the
 * video's comments load again. */
function useCommentAction(action: (id: string) => Promise<void>, done: string) {
  const queryClient = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: ({ id }: { id: string; videoId: string }) => action(id),
    onSuccess: (_data, { videoId }) => {
      toast(done)
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: moderationKeys.all }),
        queryClient.invalidateQueries({ queryKey: commentKeys.all(videoId) }),
        queryClient.invalidateQueries({ queryKey: videoKeys.detail(videoId) }),
      ])
    },
  })
}

export function useDeleteComment() {
  return useCommentAction(deleteComment, 'Comment deleted')
}

export function useDismissComment() {
  return useCommentAction(dismissComment, 'Reports dismissed')
}
