import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { json, mockApi } from '../test/api'
import { intersectAll } from '../test/observers'
import { renderApp } from '../test/render'
import { page, summary } from '../test/videos'

const cards = () => screen.getAllByRole('article')
const ME = { 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) }

describe('HomePage', () => {
  it('shows skeletons, then cards with channel, views and age', async () => {
    mockApi({
      ...ME,
      'GET /api/videos': () =>
        json(200, page([summary(1, { title: 'Big Buck Bunny – trailer', view_count: 2_384_112 })])),
    })
    renderApp('/')
    expect(screen.getByLabelText('Loading videos')).toHaveAttribute('aria-busy', 'true')

    const link = await screen.findByRole('link', { name: 'Big Buck Bunny – trailer' })
    expect(link).toHaveAttribute('href', '/watch?v=video-00001')
    const card = cards()[0]
    expect(within(card).getByRole('link', { name: 'Open Movie Club' })).toHaveAttribute(
      'href',
      '/@openmovieclub',
    )
    expect(within(card).getByText(/^2\.3M views • 3 days ago$/)).toBeInTheDocument()
    expect(within(card).getByText('0:33')).toBeInTheDocument()
  })

  it('loads the next page by its cursor when the end of the grid comes into view', async () => {
    const fetch = mockApi({
      ...ME,
      'GET /api/videos': (request) =>
        new URL(request.url).searchParams.get('cursor') === 'next'
          ? json(200, page([summary(2)]))
          : json(200, page([summary(1)], 'next')),
    })
    renderApp('/')
    await screen.findByRole('link', { name: 'Video 1' })
    expect(cards()).toHaveLength(1)

    act(() => intersectAll())
    await screen.findByRole('link', { name: 'Video 2' })
    expect(cards()).toHaveLength(2)
    const urls = fetch.mock.calls.map(([request]) => new URL(request.url))
    expect(urls.filter((url) => url.pathname === '/api/videos').map((url) => url.search)).toEqual([
      '',
      '?cursor=next',
    ])
  })

  it('says so when there are no videos yet', async () => {
    mockApi({ ...ME, 'GET /api/videos': () => json(200, page([])) })
    renderApp('/')

    expect(await screen.findByText('No videos yet')).toBeInTheDocument()
  })

  it('offers a retry when the feed fails to load', async () => {
    let calls = 0
    mockApi({
      ...ME,
      'GET /api/videos': () =>
        ++calls === 1 ? json(500, { detail: 'Server error' }) : json(200, page([summary(1)])),
    })
    renderApp('/')

    expect(await screen.findByRole('alert')).toHaveTextContent('Can’t load videos')
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('link', { name: 'Video 1' })).toBeInTheDocument()
  })
})
