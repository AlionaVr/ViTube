import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { json, mockApi } from '../test/api'
import { useViewReport } from './useViewReport'

const START = 'POST /api/videos/{id}/views/start'
const FINISH = 'POST /api/videos/{id}/views'

/** Answers both view routes for the given ids; returns the requests as "METHOD /path". */
function mockViews(ids: string[], startStatus = 204) {
  const handlers = Object.fromEntries(
    ids.flatMap((id) => [
      [START.replace('{id}', id), () => json(startStatus)],
      [FINISH.replace('{id}', id), () => json(204)],
    ]),
  )
  const fetch = mockApi(handlers)
  return () =>
    fetch.mock.calls.map(([request]) => `${request.method} ${new URL(request.url).pathname}`)
}

/** Requests go out after a few promise steps; let them. */
const settle = () => new Promise((resolve) => setTimeout(resolve, 0))

function report(id: string, durationSec: number) {
  return renderHook(({ id, durationSec }) => useViewReport(id, durationSec), {
    initialProps: { id, durationSec },
  })
}

describe('useViewReport', () => {
  it('starts once, then counts once after 30 s of playback', async () => {
    const requests = mockViews(['abc'])
    const { result } = report('abc', 600)

    result.current(0)
    result.current(29.9)
    await settle()
    expect(requests()).toEqual(['POST /api/videos/abc/views/start'])

    result.current(30)
    result.current(45)
    await settle()
    expect(requests()).toEqual(['POST /api/videos/abc/views/start', 'POST /api/videos/abc/views'])
  })

  it('counts a short video once it played to the end, and at least 1 s', async () => {
    const requests = mockViews(['short', 'tiny'])
    const { result, rerender } = report('short', 5)

    result.current(4.9)
    result.current(5)
    await waitFor(() => expect(requests()).toContain('POST /api/videos/short/views'))

    rerender({ id: 'tiny', durationSec: 0 })
    result.current(0.5)
    await settle()
    expect(requests()).not.toContain('POST /api/videos/tiny/views')
    result.current(1)
    await waitFor(() => expect(requests()).toContain('POST /api/videos/tiny/views'))
  })

  it('reports the next video afresh', async () => {
    const requests = mockViews(['one', 'two'])
    const { result, rerender } = report('one', 10)
    result.current(10)
    await waitFor(() => expect(requests()).toContain('POST /api/videos/one/views'))

    rerender({ id: 'two', durationSec: 10 })
    result.current(10)
    await waitFor(() => expect(requests()).toContain('POST /api/videos/two/views'))
    expect(requests()).toContain('POST /api/videos/two/views/start')
  })

  it('sends no count when the start failed', async () => {
    const requests = mockViews(['abc'], 404)
    const { result } = report('abc', 10)

    result.current(0)
    result.current(10)
    await settle()
    expect(requests()).toEqual(['POST /api/videos/abc/views/start'])
  })
})
