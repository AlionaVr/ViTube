import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ANNA, json, mockApi } from '../../test/api'
import { channel } from '../../test/channels'
import { renderApp } from '../../test/render'
import { setScreenWidth } from '../../test/screen'
import { comment, detail, page, summary } from '../../test/videos'
import type { Rating, Video } from '../../videos/types'

const VIDEO = detail(1, { title: 'Sintel – trailer', view_count: 1_920_441 })
const SIGNED_IN = { 'GET /api/auth/me': () => json(200, ANNA) }
const GUEST = { 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) }

/** The API of one watch page; the rating and new comments behave like the server's. */
interface HistoryState {
  progress?: Record<string, number>
  paused?: boolean
}

function mockWatch(video: Video = VIDEO, viewer = SIGNED_IN, history: HistoryState = {}) {
  const base = `/api/videos/${video.id}`
  const owner = `/api/channels/${video.channel.handle}`
  const subscribed = (is_subscribed: boolean) => () =>
    json(200, { subscriber_count: 2 + (is_subscribed ? 1 : 0), is_subscribed })
  return mockApi({
    ...viewer,
    [`GET ${base}`]: () => json(200, video),
    [`GET ${owner}`]: () => json(200, channel({ ...video.channel, subscriber_count: 2 })),
    [`GET ${base}/saved`]: () => json(200, { saved: false }),
    [`PUT ${owner}/subscription`]: subscribed(true),
    [`DELETE ${owner}/subscription`]: subscribed(false),
    [`GET ${base}/related`]: () => json(200, page([2, 3, 4].map((n) => summary(n)))),
    [`GET ${base}/comments`]: () => json(200, page([comment(1)])),
    [`POST ${base}/comments`]: async (request) => {
      const { text } = (await request.json()) as { text: string }
      const author = { handle: ANNA.handle, name: ANNA.handle, avatar_url: null }
      return json(201, comment(2, { text, author, published_at: new Date().toISOString() }))
    },
    [`POST ${base}/views/start`]: () => json(204),
    [`POST ${base}/views`]: () => json(204),
    [`PUT /api/me/history/${video.id}`]: () => json(204),
    'GET /api/me/history/progress': () => json(200, history.progress ?? {}),
    'GET /api/me/history/settings': () => json(200, { paused: history.paused ?? false }),
    [`PUT ${base}/rating`]: async (request) => {
      const { rating } = (await request.json()) as { rating: Rating }
      return json(200, {
        like_count: video.like_count + (rating === 'like' ? 1 : 0),
        my_rating: rating,
      })
    },
  })
}

// A body reads once; waitFor asks again and again.
const positions = new WeakMap<Request, Promise<number>>()

/** Positions saved to the history, in order. */
function savedPositions(fetch: ReturnType<typeof mockApi>): Promise<number[]> {
  const saves = fetch.mock.calls
    .map(([request]) => request)
    .filter((request) => request.method === 'PUT' && request.url.includes('/api/me/history/'))
  return Promise.all(
    saves.map((request) => {
      if (!positions.has(request)) {
        const body = request.json() as Promise<{ position_sec: number }>
        positions.set(
          request,
          body.then((saved) => saved.position_sec),
        )
      }
      return positions.get(request)!
    }),
  )
}

async function openWatch(video: Video = VIDEO) {
  const router = renderApp(`/watch?v=${video.id}`)
  await screen.findByRole('heading', { level: 1, name: video.title })
  return router
}

describe('WatchPage', () => {
  afterEach(() => localStorage.clear())

  it('shows the video, its channel, description and Up next', async () => {
    mockWatch()
    await openWatch()
    // The player waits for where the viewer stopped.
    expect(await screen.findByRole('region', { name: 'Video player' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open Movie Club' })).toHaveAttribute(
      'href',
      '/@openmovieclub',
    )
    expect(document.title).toBe('Sintel – trailer - ViTube')

    const upNext = await screen.findByRole('region', { name: 'Up next' })
    expect(within(upNext).getByRole('link', { name: /Video 2/ })).toHaveAttribute(
      'href',
      '/watch?v=video-00002',
    )
  })

  it('reports playback for the view count: start at once, the view after 30 s played', async () => {
    const fetch = mockWatch()
    await openWatch()
    const sent = () =>
      fetch.mock.calls
        .map(([request]) => `${request.method} ${new URL(request.url).pathname}`)
        .filter((call) => call.includes('/views'))
    // The player autoplays.
    await waitFor(() => expect(sent()).toEqual(['POST /api/videos/video-00001/views/start']))

    const video = document.querySelector('video')!
    Object.defineProperty(video, 'played', { value: { length: 1, start: () => 0, end: () => 30 } })
    fireEvent.timeUpdate(video)
    await waitFor(() =>
      expect(sent()).toEqual([
        'POST /api/videos/video-00001/views/start',
        'POST /api/videos/video-00001/views',
      ]),
    )
  })

  it('saves the position to the history on start and pause, and every 10 s while playing', async () => {
    const now = vi.spyOn(Date, 'now').mockReturnValue(1_000_000)
    const fetch = mockWatch()
    await openWatch()
    // The player autoplays from the start.
    await waitFor(async () => expect(await savedPositions(fetch)).toEqual([0]))

    const video = document.querySelector('video')!
    video.currentTime = 4
    now.mockReturnValue(1_010_000)
    video.currentTime = 12.7
    video.currentTime = 13
    video.pause()
    await waitFor(async () => expect(await savedPositions(fetch)).toEqual([0, 12, 13]))
    now.mockRestore()
  })

  it('saves the last position when the tab closes', async () => {
    const fetch = mockWatch()
    await openWatch()
    await waitFor(async () => expect(await savedPositions(fetch)).toEqual([0]))

    document.querySelector('video')!.currentTime = 7
    window.dispatchEvent(new Event('pagehide'))
    await waitFor(async () => expect(await savedPositions(fetch)).toEqual([0, 7]))
    expect(fetch.mock.calls.at(-1)![0].keepalive).toBe(true)
  })

  it('starts where the viewer stopped', async () => {
    mockWatch(VIDEO, SIGNED_IN, { progress: { [VIDEO.id]: 20 } })
    await openWatch()
    await screen.findByRole('region', { name: 'Video player' })
    expect(document.querySelector('video')!.getAttribute('src')).toBe(`${VIDEO.media_url}#t=20`)
  })

  it('starts over a video the viewer saw to the end', async () => {
    // 33 s long: the last 5 s count as the end.
    mockWatch(VIDEO, SIGNED_IN, { progress: { [VIDEO.id]: 28 } })
    await openWatch()
    await screen.findByRole('region', { name: 'Video player' })
    expect(document.querySelector('video')!.getAttribute('src')).toBe(VIDEO.media_url)
  })

  it('saves nothing while the viewer has paused the history', async () => {
    const fetch = mockWatch(VIDEO, SIGNED_IN, { paused: true })
    await openWatch()
    const calls = () => fetch.mock.calls.map(([request]) => new URL(request.url).pathname)
    await waitFor(() => expect(calls()).toContain('/api/me/history/settings'))
    const video = document.querySelector('video')!
    video.currentTime = 12
    video.pause()
    window.dispatchEvent(new Event('pagehide'))
    expect(await savedPositions(fetch)).toEqual([])
  })

  it('keeps no history for a guest', async () => {
    const fetch = mockWatch(VIDEO, GUEST)
    await openWatch()
    const calls = () => fetch.mock.calls.map(([request]) => new URL(request.url).pathname)
    await waitFor(() => expect(calls()).toContain('/api/videos/video-00001/views/start'))
    document.querySelector('video')!.pause()
    expect(await savedPositions(fetch)).toEqual([])
  })

  it('sets off fireworks for a like, not for taking it back', async () => {
    mockWatch()
    await openWatch()
    const like = screen.getByRole('button', { name: /^Like this video along with/ })
    const fireworks = () => like.querySelectorAll('[data-fireworks]')

    await userEvent.click(like)
    expect(fireworks()).toHaveLength(1)
    fireEvent.animationEnd(fireworks()[0])
    expect(fireworks()).toHaveLength(0)

    await userEvent.click(like)
    expect(like).toHaveAttribute('aria-pressed', 'false')
    expect(fireworks()).toHaveLength(0)
  })

  it('likes and unlikes at once, with the count', async () => {
    mockWatch()
    await openWatch()
    const like = screen.getByRole('button', { name: 'Like this video along with 120 other people' })
    expect(like).toHaveAttribute('aria-pressed', 'false')

    await userEvent.click(like)
    expect(like).toHaveAttribute('aria-pressed', 'true')
    expect(like).toHaveTextContent('121')

    await userEvent.click(screen.getByRole('button', { name: 'Dislike this video' }))
    expect(screen.getByRole('button', { name: 'Dislike this video' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(like).toHaveAttribute('aria-pressed', 'false')
    expect(like).toHaveTextContent('120')
  })

  it('shows the channel’s subscribers and subscribes from here', async () => {
    mockWatch()
    await openWatch()
    expect(await screen.findByText('2 subscribers')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Subscribe' }))

    expect(await screen.findByRole('button', { name: /Subscribed/ })).toBeInTheDocument()
    expect(screen.getByText('3 subscribers')).toBeInTheDocument()
  })

  it('shows no Subscribe on your own video', async () => {
    const own = detail(1, { channel: { handle: ANNA.handle, name: ANNA.handle, avatar_url: null } })
    mockWatch(own)
    await openWatch(own)

    expect(await screen.findByText('2 subscribers')).toBeInTheDocument()
    await screen.findByRole('button', { name: 'Account menu' }) // the viewer is known
    expect(screen.queryByRole('button', { name: /Subscribe/ })).not.toBeInTheDocument()
  })

  it('expands and collapses the description', async () => {
    mockWatch()
    await openWatch()
    await userEvent.click(screen.getByRole('button', { name: 'more' }))
    expect(screen.getByText(/^1,920,441 views$/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Show less' }))
    expect(screen.getByText('1.9M views')).toBeInTheDocument()
  })

  it('lists comments and posts a new one at the top', async () => {
    mockWatch()
    await openWatch()
    expect(await screen.findByText('Comment 1')).toBeInTheDocument()
    const box = screen.getByRole('textbox', { name: 'Add a comment…' })
    await userEvent.click(box)
    const submit = screen.getByRole('button', { name: 'Comment' })
    expect(submit).toBeDisabled()

    await userEvent.type(box, 'Beautiful trailer!')
    await userEvent.click(submit)

    const first = (await screen.findAllByRole('article'))[0]
    await within(first).findByText('Beautiful trailer!')
    expect(within(first).getByText(`@${ANNA.handle}`)).toBeInTheDocument()
    expect(box).toHaveValue('')
  })

  it('asks a guest to sign in instead of liking', async () => {
    mockWatch(VIDEO, GUEST)
    await openWatch()

    await userEvent.click(screen.getByRole('button', { name: /^Like this video along with/ }))
    const prompt = screen.getByRole('dialog', { name: 'Like this video?' })
    expect(prompt).toHaveTextContent('Sign in to make your opinion count.')
    expect(within(prompt).getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')

    expect(document.querySelector('[data-fireworks]')).not.toBeInTheDocument()

    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'Like this video?' })).not.toBeInTheDocument()
  })

  it('puts Up next under the description on narrow screens', async () => {
    setScreenWidth(900)
    mockWatch()
    await openWatch()
    const upNext = await screen.findByRole('region', { name: 'Up next' })
    const comments = screen.getByRole('region', { name: '1 Comment' })
    expect(upNext.compareDocumentPosition(comments)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  })

  it('tells the owner why their video can’t play yet, without ratings or comments', async () => {
    const failed = detail(1, {
      status: 'failed',
      error_message: 'The file is not a video',
      media_url: null,
      thumbnail_url: null,
    })
    mockWatch(failed)
    await openWatch(failed)

    expect(screen.getByRole('alert')).toHaveTextContent('Processing failedThe file is not a video')
    expect(screen.queryByRole('region', { name: 'Video player' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Like this video/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '1 Comment' })).not.toBeInTheDocument()
  })

  it('says the video is unavailable for an unknown id', async () => {
    mockApi({
      ...GUEST,
      'GET /api/videos/nope': () => json(404, { detail: 'Video not found' }),
      'GET /api/videos/nope/related': () => json(404, { detail: 'Video not found' }),
    })
    renderApp('/watch?v=nope')
    expect(await screen.findByText('Video unavailable')).toBeInTheDocument()
  })
})
