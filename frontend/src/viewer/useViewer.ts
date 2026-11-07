import type { User } from '../api/client'
import { useMe } from '../auth/hooks'

/** Who is watching. The only place the UI learns it from. */
export type Viewer =
  { status: 'loading' } | { status: 'guest' } | { status: 'authenticated'; user: User }

// A failed /me (API down) shows the guest UI rather than nothing.
export function useViewer(): Viewer {
  const { data, isPending } = useMe()
  if (isPending) return { status: 'loading' }
  return data ? { status: 'authenticated', user: data } : { status: 'guest' }
}
