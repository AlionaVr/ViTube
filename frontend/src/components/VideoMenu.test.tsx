import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { describe, expect, it } from 'vitest'

import { createQueryClient } from '../api/queryClient'
import { ANNA, json, mockApi } from '../test/api'
import { playlist } from '../test/playlists'
import { renderApp } from '../test/render'
import { page, summary } from '../test/videos'
import CompactVideoCard from './CompactVideoCard'

const GUEST = { 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) }
const SIGNED_IN = {
  'GET /api/auth/me': () => json(200, ANNA),
  'GET /api/me/subscriptions': () => json(200, page([])),
  'GET /api/me/history/progress': () => json(200, {}),
}
const HOME = {
  'GET /api/categories': () => json(200, []),
  'GET /api/videos': () => json(200, page([summary(1), summary(2)])),
}
const WATCH_LATER = playlist(9, { title: 'Watch later', kind: 'watch_later' })

/** Opens ⋮ on the home page's card `n` (0-based) and lists its choices. */
async function openMenu(n: number) {
  const user = userEvent.setup() // a clipboard, as a secure page has
  const cards = await screen.findAllByRole('article')
  await user.click(within(cards[n]).getByRole('button', { name: 'Action menu' }))
  return { user, choices: screen.getAllByRole('menuitem').map((choice) => choice.textContent) }
}

describe('⋮ on video cards', () => {
  it('offers a signed-in viewer save and share', async () => {
    mockApi({ ...SIGNED_IN, ...HOME })
    renderApp('/')

    const { choices } = await openMenu(0)

    expect(choices).toEqual(['Save to Watch later', 'Save to playlist', 'Share'])
  })

  it('saves the card’s video to Watch later and says so', async () => {
    const sent: string[] = []
    mockApi({
      ...SIGNED_IN,
      ...HOME,
      'GET /api/me/watch-later': () => json(200, WATCH_LATER),
      [`PUT /api/playlists/${WATCH_LATER.id}/items/video-00002`]: (request) => {
        sent.push(new URL(request.url).pathname)
        return json(204)
      },
    })
    renderApp('/')

    const { user } = await openMenu(1)
    await user.click(screen.getByRole('menuitem', { name: 'Save to Watch later' }))

    expect(await screen.findByText('Saved to Watch later')).toBeInTheDocument()
    expect(sent).toEqual([`/api/playlists/${WATCH_LATER.id}/items/video-00002`])
  })

  it('opens the Save dialog for the card’s video', async () => {
    mockApi({ ...SIGNED_IN, ...HOME, 'GET /api/me/playlists': () => json(200, page([])) })
    renderApp('/')

    const { user } = await openMenu(1)
    await user.click(screen.getByRole('menuitem', { name: 'Save to playlist' }))

    expect(screen.getByRole('dialog', { name: 'Save video to...' })).toBeInTheDocument()
  })

  it('gives a guest Share only, and copying the link says so in a toast', async () => {
    mockApi({ ...GUEST, ...HOME })
    renderApp('/')

    const { user, choices } = await openMenu(1)
    expect(choices).toEqual(['Share'])
    await user.click(screen.getByRole('menuitem', { name: 'Share' }))
    const dialog = screen.getByRole('dialog', { name: 'Share' })
    await user.click(within(dialog).getByRole('button', { name: 'Copy' }))

    expect(await navigator.clipboard.readText()).toBe(
      `${window.location.origin}/watch?v=video-00002`,
    )
    expect(await screen.findByText('Link copied to clipboard')).toBeInTheDocument()
  })

  it('sits beside an Up next row’s link, not inside it', async () => {
    mockApi(GUEST)
    const router = createMemoryRouter([
      { path: '/', element: <CompactVideoCard video={summary(1)} /> },
    ])
    render(
      <QueryClientProvider client={createQueryClient()}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    )

    const row = await screen.findByRole('link', { name: /Video 1/ })
    const menu = screen.getByRole('button', { name: 'Action menu' })

    expect(row).not.toContainElement(menu)
    await userEvent.click(menu)
    expect(screen.getByRole('menuitem', { name: 'Share' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/') // the click didn't open the video
  })
})
