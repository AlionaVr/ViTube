import type { Channel } from '../channels/types'

/** A channel header as the API sends it, for a guest. */
export function channel(overrides: Partial<Channel> = {}): Channel {
  return {
    handle: 'openmovieclub',
    name: 'Open Movie Club',
    avatar_url: null,
    joined_at: '2024-03-01T10:00:00Z',
    subscriber_count: 2,
    video_count: 3,
    is_subscribed: false,
    is_terminated: false,
    ...overrides,
  }
}
