import { QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'

import { createQueryClient } from '../api/queryClient'
import { ANNA, json, mockApi } from '../test/api'
import { useMe, useSignIn, useSignOut } from './hooks'

function renderAuth() {
  const queryClient = createQueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return renderHook(() => ({ me: useMe(), signIn: useSignIn(), signOut: useSignOut() }), {
    wrapper,
  })
}

describe('auth hooks', () => {
  it('give null for a guest', async () => {
    mockApi({ 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) })

    const { result } = renderAuth()

    await waitFor(() => expect(result.current.me.isSuccess).toBe(true))
    expect(result.current.me.data).toBeNull()
  })

  it('know the user right after sign in, without asking again', async () => {
    const fetch = mockApi({
      'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }),
      'POST /api/auth/login': () => json(200, ANNA),
    })
    const { result } = renderAuth()
    await waitFor(() => expect(result.current.me.data).toBeNull())

    await result.current.signIn.mutateAsync({ email: ANNA.email, password: 'whatever-123' })

    await waitFor(() => expect(result.current.me.data).toEqual(ANNA))
    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it('forget the user after sign out', async () => {
    mockApi({
      'GET /api/auth/me': () => json(200, ANNA),
      'POST /api/auth/logout': () => new Response(null, { status: 204 }),
    })
    const { result } = renderAuth()
    await waitFor(() => expect(result.current.me.data).toEqual(ANNA))

    await result.current.signOut.mutateAsync()

    await waitFor(() => expect(result.current.me.data).toBeNull())
  })
})
