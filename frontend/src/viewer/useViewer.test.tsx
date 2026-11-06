import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it } from 'vitest'

import { createQueryClient } from '../api/queryClient'
import { DEMO_USER } from '../mocks/server'
import { useSetDemoGuest, useViewer } from './useViewer'

function renderViewer() {
  const queryClient = createQueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return renderHook(() => ({ viewer: useViewer(), setGuest: useSetDemoGuest() }), { wrapper })
}

describe('useViewer', () => {
  afterEach(() => localStorage.clear())

  it('is loading first, then the demo user', async () => {
    const { result } = renderViewer()
    expect(result.current.viewer).toEqual({ status: 'loading' })

    await waitFor(() =>
      expect(result.current.viewer).toEqual({ status: 'authenticated', user: DEMO_USER }),
    )
  })

  it('becomes a guest after the demo switch, and back', async () => {
    const { result } = renderViewer()
    await waitFor(() => expect(result.current.viewer.status).toBe('authenticated'))

    act(() => result.current.setGuest(true))
    await waitFor(() => expect(result.current.viewer).toEqual({ status: 'guest' }))

    act(() => result.current.setGuest(false))
    await waitFor(() => expect(result.current.viewer.status).toBe('authenticated'))
  })
})
