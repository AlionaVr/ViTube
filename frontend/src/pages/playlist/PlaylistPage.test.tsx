import { act, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ANNA, json, mockApi } from '../../test/api'
import { intersectAll } from '../../test/observers'
import { item, playlist } from '../../test/playlists'
import { renderApp } from '../../test/render'
import { page } from '../../test/videos'

const GUEST = { 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) }
const PLAYLIST = playlist(1, {
  title: 'Blender films',
  description: 'Open movies',
  video_count: 2,
  thumbnail_url: '/media/thumbs/1.jpg',
})
const API = `/api/playlists/${PLAYLIST.id}`

describe('PlaylistPage', () => {
  it('shows the playlist and its videos in order', async () => {
    mockApi({
      ...GUEST,
      [`GET ${API}`]: () => json(200, PLAYLIST),
      [`GET ${API}/items`]: () => json(200, page([item(1), item(2)])),
    })
    renderApp(`/playlist?list=${PLAYLIST.id}`)

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Blender films' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open Movie Club' })).toHaveAttribute(
      'href',
      '/@openmovieclub',
    )
    expect(screen.getByText('Private')).toBeInTheDocument()
    expect(screen.getByText('2 videos')).toBeInTheDocument()
    expect(screen.getByText(/^Updated /)).toBeInTheDocument()
    expect(screen.getByText('Open movies')).toBeInTheDocument()
    expect(document.title).toBe('Blender films - ViTube')

    const list = await screen.findByRole('list')
    const rows = within(list).getAllByRole('listitem')
    expect(rows.map((row) => row.textContent)).toEqual([
      expect.stringMatching(/^1.*Video 1/),
      expect.stringMatching(/^2.*Video 2/),
    ])
    expect(screen.getByRole('link', { name: /Play all/ })).toHaveAttribute(
      'href',
      '/watch?v=video-00001',
    )
  })

  it('loads more videos on scroll', async () => {
    mockApi({
      ...GUEST,
      [`GET ${API}`]: () => json(200, PLAYLIST),
      [`GET ${API}/items`]: (request) =>
        new URL(request.url).searchParams.get('cursor') === 'next'
          ? json(200, page([item(2)]))
          : json(200, page([item(1)], 'next')),
    })
    renderApp(`/playlist?list=${PLAYLIST.id}`)
    await screen.findByRole('heading', { name: 'Video 1' })

    act(() => intersectAll())

    expect(await screen.findByRole('heading', { name: 'Video 2' })).toBeInTheDocument()
  })

  it('says so when the playlist is empty', async () => {
    mockApi({
      ...GUEST,
      [`GET ${API}`]: () => json(200, { ...PLAYLIST, video_count: 0, thumbnail_url: null }),
      [`GET ${API}/items`]: () => json(200, page([])),
    })
    renderApp(`/playlist?list=${PLAYLIST.id}`)

    expect(await screen.findByText('No videos in this playlist yet')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Play all/ })).not.toBeInTheDocument()
  })

  it('treats a missing or private playlist as not existing', async () => {
    const notFound = () => json(404, { detail: 'Playlist not found' })
    mockApi({ ...GUEST, [`GET ${API}`]: notFound, [`GET ${API}/items`]: notFound })
    renderApp(`/playlist?list=${PLAYLIST.id}`)

    expect(await screen.findByText('The playlist does not exist.')).toBeInTheDocument()
  })

  it.each(['/playlist', '/playlist?list=LL', '/playlist?list=nope'])(
    'needs a playlist id: %s',
    async (path) => {
      const fetch = mockApi(GUEST)
      renderApp(path)

      expect(await screen.findByText('The playlist does not exist.')).toBeInTheDocument()
      const urls = fetch.mock.calls.map(([request]) => new URL(request.url).pathname)
      expect(urls.filter((url) => url.startsWith('/api/playlists'))).toEqual([])
    },
  )

  describe('Watch later (list=WL)', () => {
    it('opens the viewer’s own Watch later', async () => {
      const watchLater = playlist(9, { title: 'Watch later', kind: 'watch_later', video_count: 1 })
      mockApi({
        'GET /api/auth/me': () => json(200, ANNA),
        'GET /api/me/subscriptions': () => json(200, page([])),
        'GET /api/me/watch-later': () => json(200, watchLater),
        [`GET /api/playlists/${watchLater.id}`]: () => json(200, watchLater),
        [`GET /api/playlists/${watchLater.id}/items`]: () => json(200, page([item(1)])),
      })
      renderApp('/playlist?list=WL')

      expect(
        await screen.findByRole('heading', { level: 1, name: 'Watch later' }),
      ).toBeInTheDocument()
      expect(await screen.findByRole('heading', { name: 'Video 1' })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Watch later' })).toHaveAttribute(
        'aria-current',
        'page',
      )
    })

    it('asks a guest to sign in', async () => {
      const fetch = mockApi(GUEST)
      renderApp('/playlist?list=WL')

      expect(
        await screen.findByRole('heading', { name: 'Save videos for later' }),
      ).toBeInTheDocument()
      const urls = fetch.mock.calls.map(([request]) => new URL(request.url).pathname)
      expect(urls.filter((url) => url.includes('playlist') || url.includes('watch-later'))).toEqual(
        [],
      )
    })
  })
})
