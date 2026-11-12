import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { videoKeys } from '../videos/hooks'
import { listSharedWith, setShared } from './api'

const sharedWithKey = (id: string) => [...videoKeys.all, 'shared-with', id] as const

export function useSharedWith(id: string) {
  return useQuery({ queryKey: sharedWithKey(id), queryFn: () => listSharedWith(id) })
}

/** Share or take back: the list refetches either way, failed or not. */
export function useSetShared(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ handle, shared }: { handle: string; shared: boolean }) =>
      setShared(id, handle, shared),
    onSettled: () => queryClient.invalidateQueries({ queryKey: sharedWithKey(id) }),
  })
}
