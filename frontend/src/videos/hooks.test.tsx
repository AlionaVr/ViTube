import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'

import { createQueryClient } from '../api/queryClient'
import { likedKeys } from '../liked/hooks'
import { json, mockApi } from '../test/api'
import { liked } from '../test/liked'
import { useRateVideo } from './hooks'

describe('useRateVideo', () => {
  it('makes Liked videos load again, its count and cover too', async () => {
    mockApi({
      'PUT /api/videos/video-00001/rating': () => json(200, { like_count: 1, my_rating: 'like' }),
    })
    const queryClient = createQueryClient()
    queryClient.setQueryData(likedKeys.summary, liked())
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => useRateVideo('video-00001'), { wrapper })

    await act(() => result.current.mutateAsync('like'))

    expect(queryClient.getQueryState(likedKeys.summary)?.isInvalidated).toBe(true)
  })
})
