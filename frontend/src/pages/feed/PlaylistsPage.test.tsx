import { act, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ANNA, json, mockApi } from '../../test/api'
import { intersectAll } from '../../test/observers'
import { playlist } from '../../test/playlists'
import { renderApp } from '../../test/render'
import { page } from '../../test/videos'

const SIGNED_IN = {
  'GET /api/auth/me': () => json(200, ANNA),
  'GET /api/me/subscriptions': () => json(200, page([])),
}
const WATCH_LATER = playlist(9, { title: 'Watch later', kind: 'watch_later', video_count: 2 })
const FILMS = playlist(1, { title: 'Blender films', visibility: 'public', video_count: 1 })
const main = () => screen.getByRole('main')

describe('PlaylistsPage', () => {
  it('shows the viewer’s playlists, Watch later first, with privacy and update time', async () => {
    mockApi({
      ...SIGNED_IN,
      'GET /api/me/playlists': () => json(200, page([WATCH_LATER, FILMS])),
    })
    renderApp('/feed/playlists')

    expect(await screen.findByRole('heading', { level: 1, name: 'Playlists' })).toBeInTheDocument()
    const titles = await within(main()).findAllByRole('heading', { level: 3 })
    expect(titles.map((title) => title.textContent)).toEqual(['Watch later', 'Blender films'])
    // Watch later opens at list=WL, as on YouTube.
    expect(within(main()).getByRole('link', { name: 'Watch later' })).toHaveAttribute(
      'href',
      '/playlist?list=WL',
    )
    const films = within(main()).getByRole('link', { name: 'Blender films' }).closest('article')!
    expect(within(films).getByText('Public • Playlist')).toBeInTheDocument()
    expect(within(films).getByText(/^Updated /)).toBeInTheDocument()
    expect(within(films).getByText('1 video')).toBeInTheDocument()
    expect(document.title).toBe('Playlists - ViTube')
  })

  it('loads more on scroll', async () => {
    mockApi({
      ...SIGNED_IN,
      'GET /api/me/playlists': (request) =>
        new URL(request.url).searchParams.get('cursor') === 'next'
          ? json(200, page([FILMS]))
          : json(200, page([WATCH_LATER], 'next')),
    })
    renderApp('/feed/playlists')
    await within(main()).findByRole('link', { name: 'Watch later' })

    act(() => intersectAll())

    expect(await screen.findByRole('link', { name: 'Blender films' })).toBeInTheDocument()
  })

  it('asks a guest to sign in', async () => {
    const fetch = mockApi({ 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) })
    renderApp('/feed/playlists')

    expect(
      await screen.findByRole('heading', { name: 'Enjoy your favorite videos' }),
    ).toBeInTheDocument()
    const urls = fetch.mock.calls.map(([request]) => new URL(request.url).pathname)
    expect(urls).not.toContain('/api/me/playlists')
  })
})
