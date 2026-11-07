import { QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'

import { createQueryClient } from '../api/queryClient'
import { ANNA, json, mockApi } from '../test/api'
import { useViewer } from './useViewer'

function renderViewer() {
  const queryClient = createQueryClient()
  // Errors show at once; the retry policy has its own tests.
  queryClient.setDefaultOptions({ queries: { retry: false } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return renderHook(() => useViewer(), { wrapper })
}

describe('useViewer', () => {
  it('is loading first, then the signed-in user', async () => {
    mockApi({ 'GET /api/auth/me': () => json(200, ANNA) })
    const { result } = renderViewer()
    expect(result.current).toEqual({ status: 'loading' })

    await waitFor(() => expect(result.current).toEqual({ status: 'authenticated', user: ANNA }))
  })

  it('is a guest without a session', async () => {
    mockApi({ 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) })
    const { result } = renderViewer()

    await waitFor(() => expect(result.current).toEqual({ status: 'guest' }))
  })

  it('is a guest when the API is down', async () => {
    mockApi({ 'GET /api/auth/me': () => json(503) })
    const { result } = renderViewer()

    await waitFor(() => expect(result.current).toEqual({ status: 'guest' }))
  })
})
