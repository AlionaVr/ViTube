import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'

import { ANNA, json, mockApi } from '../../test/api'
import { renderApp } from '../../test/render'
import { setScreenWidth } from '../../test/screen'
import { comment, detail, page, summary } from '../../test/videos'
import type { Rating, Video } from '../../videos/types'

const VIDEO = detail(1, { title: 'Sintel – trailer', view_count: 1_920_441 })
const SIGNED_IN = { 'GET /api/auth/me': () => json(200, ANNA) }
const GUEST = { 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) }

/** The API of one watch page; the rating and new comments behave like the server's. */
function mockWatch(video: Video = VIDEO, viewer = SIGNED_IN) {
  const base = `/api/videos/${video.id}`
  return mockApi({
    ...viewer,
    [`GET ${base}`]: () => json(200, video),
    [`GET ${base}/related`]: () => json(200, page([2, 3, 4].map((n) => summary(n)))),
    [`GET ${base}/comments`]: () => json(200, page([comment(1)])),
    [`POST ${base}/comments`]: async (request) => {
      const { text } = (await request.json()) as { text: string }
      const author = { handle: ANNA.handle, name: ANNA.handle, avatar_url: null }
      return json(201, comment(2, { text, author, published_at: new Date().toISOString() }))
    },
    [`PUT ${base}/rating`]: async (request) => {
      const { rating } = (await request.json()) as { rating: Rating }
      return json(200, {
        like_count: video.like_count + (rating === 'like' ? 1 : 0),
        my_rating: rating,
      })
    },
  })
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
    expect(screen.getByRole('region', { name: 'Video player' })).toBeInTheDocument()
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

  it('expands and collapses the description', async () => {
    mockWatch()
    await openWatch()
    await userEvent.click(screen.getByRole('button', { name: '...more' }))
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
