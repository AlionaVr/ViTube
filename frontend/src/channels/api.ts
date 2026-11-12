// Channels API.
import { api, unwrap } from '../api/client'
import type { Page, VideoSummary } from '../videos/types'
import type { Channel, MyChannelVideo, SubscribedChannel, Subscription, VideoSort } from './types'

/** Throws ApiError 404 for an unknown handle. */
export function getChannel(handle: string): Promise<Channel> {
  return unwrap(api.GET('/api/channels/{handle}', { params: { path: { handle } } }))
}

/** The Videos tab: public, ready videos only. */
export function listChannelVideos(
  handle: string,
  sort: VideoSort,
  cursor: string | null,
): Promise<Page<VideoSummary>> {
  return unwrap(
    api.GET('/api/channels/{handle}/videos', {
      params: { path: { handle }, query: { sort, cursor } },
    }),
  )
}

/** Your own channel's Videos tab: every ready video of yours. Throws ApiError 401 for a guest. */
export function listMyChannelVideos(
  sort: VideoSort,
  cursor: string | null,
): Promise<Page<MyChannelVideo>> {
  return unwrap(api.GET('/api/me/channel/videos', { params: { query: { sort, cursor } } }))
}

/** Throws ApiError 401 for a guest, 400 on your own channel. */
export function setSubscribed(handle: string, subscribed: boolean): Promise<Subscription> {
  const params = { params: { path: { handle } } }
  return unwrap(
    subscribed
      ? api.PUT('/api/channels/{handle}/subscription', params)
      : api.DELETE('/api/channels/{handle}/subscription', params),
  )
}

/** The viewer's subscriptions, A to Z. Throws ApiError 401 for a guest. */
export function listSubscriptions(cursor: string | null): Promise<Page<SubscribedChannel>> {
  return unwrap(api.GET('/api/me/subscriptions', { params: { query: { cursor } } }))
}

/** New public videos of the viewer's subscriptions. Throws ApiError 401 for a guest. */
export function listSubscriptionsFeed(cursor: string | null): Promise<Page<VideoSummary>> {
  return unwrap(api.GET('/api/feed/subscriptions', { params: { query: { cursor } } }))
}
