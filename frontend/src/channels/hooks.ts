import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { Video } from '../videos/types'
import { videoKeys } from '../videos/hooks'
import { listSubscriptions, setSubscribed } from './api'

const SUBSCRIPTIONS = ['subscriptions'] as const

export function useSubscriptions() {
  return useQuery({ queryKey: SUBSCRIPTIONS, queryFn: listSubscriptions })
}

/** Subscribe or unsubscribe: every cached video of the channel updates at once. */
export function useSetSubscribed(handle: string) {
  const queryClient = useQueryClient()
  const update = (patch: Partial<Video['channel']>) =>
    queryClient.setQueriesData<Video>({ queryKey: videoKeys.details }, (video) =>
      video && video.channel.handle === handle
        ? { ...video, channel: { ...video.channel, ...patch } }
        : video,
    )

  return useMutation({
    mutationFn: (subscribed: boolean) => setSubscribed(handle, subscribed),
    onMutate: async (subscribed) => {
      await queryClient.cancelQueries({ queryKey: videoKeys.details })
      const previous = queryClient.getQueriesData<Video>({ queryKey: videoKeys.details })
      update({ is_subscribed: subscribed })
      return { previous }
    },
    onError: (_error, _subscribed, context) => {
      for (const [key, video] of context?.previous ?? []) queryClient.setQueryData(key, video)
    },
    onSuccess: (result) => update(result),
    onSettled: () => queryClient.invalidateQueries({ queryKey: SUBSCRIPTIONS }),
  })
}
