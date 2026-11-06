// Channels API. Reads the demo server for now; see videos/api.ts.
import * as server from '../mocks/server'
import type { ChannelSummary } from './types'

/** The viewer's subscriptions; empty for a guest. */
export function listSubscriptions(): Promise<ChannelSummary[]> {
  return server.listSubscriptions()
}

/** Throws ApiError 401 for a guest. */
export function setSubscribed(
  handle: string,
  subscribed: boolean,
): Promise<{ subscriber_count: number; is_subscribed: boolean }> {
  return server.setSubscribed(handle, subscribed)
}
