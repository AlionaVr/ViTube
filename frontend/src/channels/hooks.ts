import { useQuery } from '@tanstack/react-query'

import { listSubscriptions } from './api'

const SUBSCRIPTIONS = ['subscriptions'] as const

export function useSubscriptions() {
  return useQuery({ queryKey: SUBSCRIPTIONS, queryFn: listSubscriptions })
}
