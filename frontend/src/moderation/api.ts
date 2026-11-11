// Moderation API (ADR 0009): the report queue and moderator actions.
import { api, unwrap } from '../api/client'
import type { components } from '../api/schema'

export type ReportReason = components['schemas']['ReportReason']
export type ReportCase = components['schemas']['ReportCase']
export type ModeratedVideo = components['schemas']['ModeratedVideo']
export type ReportPage = components['schemas']['Page_ReportCase_']

/** Open reports grouped by video, oldest first. Throws ApiError 403 for a non-moderator. */
export function listReports(cursor: string | null): Promise<ReportPage> {
  return unwrap(api.GET('/api/moderation/reports', { params: { query: { cursor } } }))
}

/** Hides the video from everyone but its owner and moderators; closes its reports. */
export async function hideVideo(id: string, reason: ReportReason): Promise<void> {
  await unwrap(
    api.POST('/api/moderation/videos/{public_id}/hide', {
      params: { path: { public_id: id } },
      body: { reason },
    }),
  )
}

export type HiddenPage = components['schemas']['Page_ModeratedVideo_']

/** Hidden videos, newest first. */
export function listHidden(cursor: string | null): Promise<HiddenPage> {
  return unwrap(api.GET('/api/moderation/videos/hidden', { params: { query: { cursor } } }))
}

/** Shows a hidden video to everyone who could watch it before. */
export async function restoreVideo(id: string): Promise<void> {
  await unwrap(
    api.POST('/api/moderation/videos/{public_id}/restore', { params: { path: { public_id: id } } }),
  )
}

/** Closes the video's open reports: nothing wrong with it. */
export async function dismissVideo(id: string): Promise<void> {
  await unwrap(
    api.POST('/api/moderation/videos/{public_id}/dismiss', { params: { path: { public_id: id } } }),
  )
}

export type ModeratedComment = components['schemas']['ModeratedComment']

/** Deletes the comment for everyone; a thread's first comment takes its replies along. */
export async function deleteComment(id: string): Promise<void> {
  await unwrap(
    api.DELETE('/api/moderation/comments/{comment_id}', { params: { path: { comment_id: id } } }),
  )
}

/** Closes the comment's open reports: nothing wrong with it. */
export async function dismissComment(id: string): Promise<void> {
  await unwrap(
    api.POST('/api/moderation/comments/{comment_id}/dismiss', {
      params: { path: { comment_id: id } },
    }),
  )
}
