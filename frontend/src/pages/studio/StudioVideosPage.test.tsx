import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { formatDate } from '../../lib/format'
import { ANNA, json, mockApi } from '../../test/api'
import { intersectAll } from '../../test/observers'
import { renderApp } from '../../test/render'
import { own, page } from '../../test/videos'
import type { VideoStatus } from '../../videos/types'

const SIGNED_IN = { 'GET /api/auth/me': () => json(200, ANNA) }

/** The query string of each list request, in order. */
const listRequests = (fetch: ReturnType<typeof mockApi>) =>
  fetch.mock.calls
    .map(([request]) => new URL(request.url))
    .filter((url) => url.pathname === '/api/me/videos')
    .map((url) => url.search)

const rowOf = (title: string) => {
  const row = screen.getByRole('link', { name: title }).closest('tr')
  if (!row) throw new Error(`No row for ${title}`)
  return within(row)
}

describe('StudioVideosPage', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('sends a guest to sign in and back here', async () => {
    const router = renderApp('/studio/videos')

    await screen.findByRole('heading', { name: 'Sign in' })
    expect(router.state.location.pathname).toBe('/login')
    expect(router.state.location.state).toEqual({ from: '/studio/videos' })
  })

  it('shows skeleton rows while the list loads', async () => {
    mockApi({ ...SIGNED_IN, 'GET /api/me/videos': () => new Promise<Response>(() => {}) })
    renderApp('/studio/videos')

    expect(await screen.findByRole('table', { name: 'Loading videos' })).toHaveAttribute(
      'aria-busy',
      'true',
    )
  })

  it('lists every video with its visibility, status, date and counts', async () => {
    const ready = own(1, {
      title: 'Sintel – trailer',
      description: 'A lone girl searches for a baby dragon.',
      visibility: 'public',
      view_count: 2_384_112,
      comment_count: 12,
      like_count: 1_204,
    })
    mockApi({
      ...SIGNED_IN,
      'GET /api/me/videos': () =>
        json(
          200,
          page([
            ready,
            own(2, {
              title: 'Still processing',
              status: 'processing',
              visibility: 'unlisted',
              thumbnail_url: null,
              duration_sec: null,
            }),
            own(3, {
              title: 'Never uploaded',
              status: 'uploading',
              visibility: 'private',
              thumbnail_url: null,
              duration_sec: null,
            }),
          ]),
        ),
    })
    renderApp('/studio/videos')

    expect(await screen.findByRole('link', { name: 'Sintel – trailer' })).toHaveAttribute(
      'href',
      '/watch?v=video-00001',
    )
    const first = rowOf('Sintel – trailer')
    expect(first.getByText('A lone girl searches for a baby dragon.')).toBeInTheDocument()
    expect(first.getByText('Public')).toBeInTheDocument()
    expect(first.getByText('None')).toBeInTheDocument()
    expect(first.getByText('Ready')).toBeInTheDocument()
    expect(first.getByText(formatDate(ready.created_at))).toBeInTheDocument()
    expect(first.getByText('Published')).toBeInTheDocument()
    expect(first.getByText('2,384,112')).toBeInTheDocument()
    expect(first.getByText('12')).toBeInTheDocument()
    expect(first.getByText('1,204')).toBeInTheDocument()

    const processing = rowOf('Still processing')
    expect(processing.getByText('Unlisted')).toBeInTheDocument()
    expect(processing.getByText('Processing')).toBeInTheDocument()
    expect(processing.getByText('Uploaded')).toBeInTheDocument()
    // A draft says so in Visibility, as in Studio, and only there.
    const draft = rowOf('Never uploaded')
    expect(draft.getByText('Draft')).toBeInTheDocument()
    expect(draft.queryByText('Private')).not.toBeInTheDocument()
    expect(document.title).toBe('Channel content - ViTube')
  })

  it('shows a video a moderator hid in Restrictions', async () => {
    mockApi({
      ...SIGNED_IN,
      'GET /api/me/videos': () =>
        json(200, page([own(1, { title: 'Fake giveaway', is_hidden: true })])),
    })
    renderApp('/studio/videos')

    await screen.findByRole('link', { name: 'Fake giveaway' })
    expect(rowOf('Fake giveaway').getByText('Hidden by a moderator')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Restrictions' })).toBeInTheDocument()
  })

  it('says why a video failed to process', async () => {
    mockApi({
      ...SIGNED_IN,
      'GET /api/me/videos': () =>
        json(
          200,
          page([
            own(1, {
              title: 'Broken file',
              status: 'failed',
              error_message: 'The file is not a video',
              thumbnail_url: null,
              duration_sec: null,
            }),
          ]),
        ),
    })
    renderApp('/studio/videos')

    await screen.findByRole('link', { name: 'Broken file' })
    expect(rowOf('Broken file').getByText('Processing failed')).toBeInTheDocument()
    expect(rowOf('Broken file').getByText('The file is not a video')).toBeInTheDocument()
  })

  it('loads the next page by its cursor when the end of the list comes into view', async () => {
    const fetch = mockApi({
      ...SIGNED_IN,
      'GET /api/me/videos': (request) =>
        new URL(request.url).searchParams.get('cursor') === 'next'
          ? json(200, page([own(2)]))
          : json(200, page([own(1)], 'next')),
    })
    renderApp('/studio/videos')
    await screen.findByRole('link', { name: 'Video 1' })

    act(() => intersectAll())
    expect(await screen.findByRole('link', { name: 'Video 2' })).toBeInTheDocument()
    expect(listRequests(fetch)).toEqual(['', '?cursor=next'])
  })

  it('shows the new status while a video processes, then stops asking', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let status: VideoStatus = 'processing'
    const fetch = mockApi({
      ...SIGNED_IN,
      'GET /api/me/videos': () => json(200, page([own(1, { status })])),
    })
    renderApp('/studio/videos')
    expect(await screen.findByText('Processing')).toBeInTheDocument()

    status = 'ready'
    await act(() => vi.advanceTimersByTimeAsync(2000))
    expect(await screen.findByText('Ready')).toBeInTheDocument()

    const asked = listRequests(fetch).length
    await act(() => vi.advanceTimersByTimeAsync(10_000))
    expect(listRequests(fetch)).toHaveLength(asked)
  })

  it('says so when the user has no videos', async () => {
    mockApi({ ...SIGNED_IN, 'GET /api/me/videos': () => json(200, page([])) })
    renderApp('/studio/videos')

    expect(await screen.findByText('No content available')).toBeInTheDocument()
  })

  it('offers a retry when the list fails to load', async () => {
    let calls = 0
    mockApi({
      ...SIGNED_IN,
      'GET /api/me/videos': () =>
        ++calls === 1 ? json(500, { detail: 'Server error' }) : json(200, page([own(1)])),
    })
    renderApp('/studio/videos')

    expect(await screen.findByRole('alert')).toHaveTextContent('Can’t load your videos')
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('link', { name: 'Video 1' })).toBeInTheDocument()
  })

  it('is where Your videos in the guide leads', async () => {
    mockApi({ ...SIGNED_IN, 'GET /api/me/videos': () => json(200, page([])) })
    renderApp('/studio/videos')

    const link = await screen.findByRole('link', { name: 'Your videos' })
    expect(link).toHaveAttribute('href', '/studio/videos')
    expect(link).toHaveAttribute('aria-current', 'page')
  })
})
