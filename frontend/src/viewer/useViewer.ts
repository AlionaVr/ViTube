import { useQuery, useQueryClient } from '@tanstack/react-query'

import type { User } from '../api/client'
import { getViewer, setDemoGuest } from '../mocks/server'

/** Who is watching. The only place the UI learns it from. */
export type Viewer =
  { status: 'loading' } | { status: 'guest' } | { status: 'authenticated'; user: User }

const VIEWER = ['demo-viewer'] as const

// Demo source for now. After the merge with feat/auth this reads useMe() (src/auth/hooks.ts):
// the same User | null, so the mapping below stays.
export function useViewer(): Viewer {
  const { data, isPending } = useQuery({ queryKey: VIEWER, queryFn: getViewer })
  if (isPending) return { status: 'loading' }
  return data ? { status: 'authenticated', user: data } : { status: 'guest' }
}

/** Dev only: switch between the demo user and a guest. Every query reloads, as after a real sign-in. */
export function useSetDemoGuest() {
  const queryClient = useQueryClient()
  return (guest: boolean) => {
    setDemoGuest(guest)
    void queryClient.resetQueries()
  }
}
