import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, api, type Credentials, unwrap, type User } from '../api/client'

const ME = ['me'] as const

/** The signed-in user, or null for a guest. */
export async function fetchMe(): Promise<User | null> {
  try {
    return await unwrap(api.GET('/api/auth/me'))
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null
    throw error
  }
}

export function useMe() {
  return useQuery({ queryKey: ME, queryFn: fetchMe })
}

// The account changed: store the new user and reload everything else, so no data of the
// previous account stays on screen.
function useAccountChange() {
  const queryClient = useQueryClient()
  return (user: User | null) => {
    queryClient.setQueryData(ME, user)
    void queryClient.resetQueries({ predicate: (query) => query.queryKey[0] !== ME[0] })
  }
}

export function useSignIn() {
  const onAccountChange = useAccountChange()
  return useMutation({
    mutationFn: (body: Credentials) => unwrap(api.POST('/api/auth/login', { body })),
    onSuccess: onAccountChange,
  })
}

export function useSignUp() {
  const onAccountChange = useAccountChange()
  return useMutation({
    mutationFn: (body: Credentials) => unwrap(api.POST('/api/auth/signup', { body })),
    onSuccess: onAccountChange,
  })
}

export function useSignOut() {
  const onAccountChange = useAccountChange()
  return useMutation({
    mutationFn: () => unwrap(api.POST('/api/auth/logout')),
    onSuccess: () => onAccountChange(null),
  })
}
