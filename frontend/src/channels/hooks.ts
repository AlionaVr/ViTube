import {
  type InfiniteData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import { videoKeys } from '../videos/hooks'
import type { Page } from '../videos/types'
import {
  getChannel,
  listChannelVideos,
  listMyChannelVideos,
  listSubscriptions,
  listSubscriptionsFeed,
  setSubscribed,
} from './api'
import type { Channel, SubscribedChannel, VideoSort } from './types'

// A (un)subscribe refetches everything under `all`: the list and the feed.
const subscriptionKeys = {
  all: ['subscriptions'] as const,
  list: ['subscriptions', 'list'] as const,
  feed: ['subscriptions', 'feed'] as const,
}

export const channelKeys = {
  // Handles are stored in lower case and matched ignoring it: /@Anna and /@anna share one entry.
  detail: (handle: string) => ['channels', 'detail', handle.toLowerCase()] as const,
  videos: (handle: string, sort: VideoSort) =>
    ['channels', 'videos', handle.toLowerCase(), sort] as const,
  // Under the owner's videos: an upload or an edit that refreshes those refreshes this too.
  myVideos: (sort: VideoSort) => [...videoKeys.mine, 'channel', sort] as const,
}

const firstPage = null as string | null

/** The viewer's subscriptions, page by page: the sidebar and /feed/channels share them. */
export function useSubscriptions() {
  return useInfiniteQuery({
    queryKey: subscriptionKeys.list,
    queryFn: ({ pageParam }) => listSubscriptions(pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
  })
}

/** /feed/subscriptions: new public videos of the viewer's subscriptions. */
export function useSubscriptionsFeed() {
  return useInfiniteQuery({
    queryKey: subscriptionKeys.feed,
    queryFn: ({ pageParam }) => listSubscriptionsFeed(pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
  })
}

/** One cache entry per channel: the channel page and the watch page show the same numbers. */
export function useChannel(handle: string) {
  return useQuery({ queryKey: channelKeys.detail(handle), queryFn: () => getChannel(handle) })
}

export function useChannelVideos(handle: string, sort: VideoSort, enabled = true) {
  return useInfiniteQuery({
    queryKey: channelKeys.videos(handle, sort),
    queryFn: ({ pageParam }) => listChannelVideos(handle, sort, pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
    enabled,
  })
}

/** Your own channel's Videos tab: every visibility (the public tab is the same for everyone). */
export function useMyChannelVideos(sort: VideoSort, enabled: boolean) {
  return useInfiniteQuery({
    queryKey: channelKeys.myVideos(sort),
    queryFn: ({ pageParam }) => listMyChannelVideos(sort, pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
    enabled,
  })
}

/** Subscribe or unsubscribe: shows at once (optimistic), the server's numbers replace it. */
export function useSetSubscribed(handle: string) {
  const queryClient = useQueryClient()
  const key = channelKeys.detail(handle)

  return useMutation({
    mutationFn: (subscribed: boolean) => setSubscribed(handle, subscribed),
    onMutate: async (subscribed) => {
      await queryClient.cancelQueries({ queryKey: key })
      await queryClient.cancelQueries({ queryKey: subscriptionKeys.list })
      const previous = queryClient.getQueryData<Channel>(key)
      const list = queryClient.getQueryData<InfiniteData<Page<SubscribedChannel>>>(
        subscriptionKeys.list,
      )
      if (previous && previous.is_subscribed !== subscribed) {
        queryClient.setQueryData<Channel>(key, {
          ...previous,
          is_subscribed: subscribed,
          subscriber_count: previous.subscriber_count + (subscribed ? 1 : -1),
        })
      }
      // An unsubscribed channel leaves the lists at once; a new one comes with the refetch.
      if (list && !subscribed) {
        const same = (item: SubscribedChannel) => item.handle === handle.toLowerCase()
        queryClient.setQueryData<InfiniteData<Page<SubscribedChannel>>>(subscriptionKeys.list, {
          ...list,
          pages: list.pages.map((page) => ({ ...page, items: page.items.filter((i) => !same(i)) })),
        })
      }
      return { previous, list }
    },
    onError: (_error, _subscribed, context) => {
      if (context?.previous) queryClient.setQueryData(key, context.previous)
      if (context?.list) queryClient.setQueryData(subscriptionKeys.list, context.list)
    },
    onSuccess: (result) => {
      queryClient.setQueryData<Channel>(key, (channel) => channel && { ...channel, ...result })
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: subscriptionKeys.all }),
  })
}
