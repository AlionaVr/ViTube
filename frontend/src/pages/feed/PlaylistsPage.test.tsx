import { act, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ANNA, json, mockApi } from '../../test/api'
import { liked } from '../../test/liked'
import { intersectAll } from '../../test/observers'
import { playlist } from '../../test/playlists'
import { renderApp } from '../../test/render'
import { page } from '../../test/videos'

const SIGNED_IN = {
  'GET /api/auth/me': () => json(200, ANNA),
  'GET /api/me/subscriptions': () => json(200, page([])),
  'GET /api/me/liked': () => json(200, liked()),
}
const WATCH_LATER = playlist(9, { title: 'Watch later', kind: 'watch_later', video_count: 2 })
const FILMS = playlist(1, { title: 'Blender films', visibility: 'public', video_count: 1 })
const main = () => screen.getByRole('main')
const card = (title: string) =>
  within(main()).getByRole('link', { name: title }).closest('article')!

describe('PlaylistsPage', () => {
  it('shows Liked videos, Watch later, then the viewer’s playlists, with privacy and update time', async () => {
    mockApi({
      ...SIGNED_IN,
      'GET /api/me/playlists': () => json(200, page([WATCH_LATER, FILMS])),
    })
    renderApp('/feed/playlists')

    expect(await screen.findByRole('heading', { level: 1, name: 'Playlists' })).toBeInTheDocument()
    const titles = await within(main()).findAllByRole('heading', { level: 3 })
    expect(titles.map((title) => title.textContent)).toEqual([
      'Liked videos',
      'Watch later',
      'Blender films',
    ])
    // As on YouTube: Liked videos opens at list=LL, Watch later at list=WL.
    expect(within(main()).getByRole('link', { name: 'Liked videos' })).toHaveAttribute(
      'href',
      '/playlist?list=LL',
    )
    expect(within(main()).getByRole('link', { name: 'Watch later' })).toHaveAttribute(
      'href',
      '/playlist?list=WL',
    )
    expect(within(card('Liked videos')).getByText('Private • Playlist')).toBeInTheDocument()
    expect(within(card('Liked videos')).getByText('2 videos')).toBeInTheDocument()
    const films = card('Blender films')
    expect(within(films).getByText('Public • Playlist')).toBeInTheDocument()
    expect(within(films).getByText(/^Updated /)).toBeInTheDocument()
    expect(within(films).getByText('1 video')).toBeInTheDocument()
    expect(document.title).toBe('Playlists - ViTube')
  })

  it('shows Liked videos without likes: no cover, no update time', async () => {
    mockApi({
      ...SIGNED_IN,
      'GET /api/me/liked': () =>
        json(200, liked({ video_count: 0, thumbnail_url: null, updated_at: null })),
      'GET /api/me/playlists': () => json(200, page([WATCH_LATER])),
    })
    renderApp('/feed/playlists')

    await within(main()).findByRole('link', { name: 'Liked videos' })
    const likes = card('Liked videos')
    expect(within(likes).getByText('No videos')).toBeInTheDocument()
    expect(within(likes).queryByText(/^Updated /)).not.toBeInTheDocument()
    expect(likes.querySelector('img')).toBeNull()
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
    expect(urls).not.toContain('/api/me/liked')
  })
})
