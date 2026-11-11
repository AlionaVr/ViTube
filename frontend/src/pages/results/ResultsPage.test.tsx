import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { json, mockApi } from '../../test/api'
import { intersectAll } from '../../test/observers'
import { renderApp } from '../../test/render'
import { page, summary } from '../../test/videos'

const GUEST = { 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) }

const result = (n: number, description = '') => ({ ...summary(n), description })
const searches = (fetch: ReturnType<typeof mockApi>) =>
  fetch.mock.calls
    .map(([request]) => new URL(request.url))
    .filter((url) => url.pathname === '/api/search')
    .map((url) => url.search)

describe('ResultsPage', () => {
  it('shows rows with the video, its channel and the start of the description', async () => {
    const fetch = mockApi({
      ...GUEST,
      'GET /api/search': () =>
        json(
          200,
          page([
            {
              ...result(1, 'A lone girl searches for the baby dragon she once saved.'),
              title: 'Sintel – trailer',
              view_count: 2_384_112,
            },
          ]),
        ),
    })
    renderApp('/results?search_query=dragon')
    expect(screen.getByLabelText('Loading results')).toHaveAttribute('aria-busy', 'true')

    const link = await screen.findByRole('link', { name: 'Sintel – trailer' })
    expect(link).toHaveAttribute('href', '/watch?v=video-00001')
    const row = screen.getByRole('article')
    expect(within(row).getByText(/^2\.3M views • 3 days ago$/)).toBeInTheDocument()
    expect(within(row).getByRole('link', { name: /Open Movie Club/ })).toHaveAttribute(
      'href',
      '/@openmovieclub',
    )
    expect(within(row).getByText(/baby dragon/)).toBeInTheDocument()
    expect(document.title).toBe('dragon - ViTube')
    expect(searches(fetch)).toEqual(['?q=dragon'])
  })

  it('loads the next page by its cursor when the end of the list comes into view', async () => {
    const fetch = mockApi({
      ...GUEST,
      'GET /api/search': (request) =>
        new URL(request.url).searchParams.get('cursor') === 'next'
          ? json(200, page([result(2)]))
          : json(200, page([result(1)], 'next')),
    })
    renderApp('/results?search_query=video')
    await screen.findByRole('link', { name: 'Video 1' })

    act(() => intersectAll())
    expect(await screen.findByRole('link', { name: 'Video 2' })).toBeInTheDocument()
    expect(searches(fetch)).toEqual(['?q=video', '?q=video&cursor=next'])
  })

  it('says so when nothing matches', async () => {
    mockApi({ ...GUEST, 'GET /api/search': () => json(200, page([])) })
    renderApp('/results?search_query=zzz')

    expect(await screen.findByText('No results found')).toBeInTheDocument()
  })

  it('offers a retry when the search fails', async () => {
    let calls = 0
    mockApi({
      ...GUEST,
      'GET /api/search': () =>
        ++calls === 1 ? json(500, { detail: 'Server error' }) : json(200, page([result(1)])),
    })
    renderApp('/results?search_query=video')

    expect(await screen.findByRole('alert')).toHaveTextContent('Can’t load results')
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('link', { name: 'Video 1' })).toBeInTheDocument()
  })

  it('goes home without a query', async () => {
    mockApi({
      ...GUEST,
      'GET /api/videos': () => json(200, page([])),
      'GET /api/categories': () => json(200, []),
    })
    const router = renderApp('/results?search_query=%20')

    expect(router.state.location.pathname).toBe('/')
  })
})
