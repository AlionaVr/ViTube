import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ANNA, json, mockApi } from '../../test/api'
import { liked, likedItem } from '../../test/liked'
import { item, mine, playlist } from '../../test/playlists'
import { renderApp } from '../../test/render'
import { page, summary } from '../../test/videos'

const WATCH_LATER = playlist(9, { kind: 'watch_later', title: 'Watch later' })

/** A signed-in viewer with something in every list, unless a list is given empty. */
function mockYou(lists: { history?: unknown[]; watchLater?: unknown[] } = {}) {
  return mockApi({
    'GET /api/auth/me': () => json(200, ANNA),
    'GET /api/me/subscriptions': () => json(200, page([])),
    'GET /api/me/history/progress': () => json(200, {}),
    'GET /api/me/history': () =>
      json(200, page(lists.history ?? [{ video: summary(1), watched_at: '2026-11-12T10:00:00Z' }])),
    'GET /api/me/playlists': () => json(200, page([mine(9, null, WATCH_LATER), mine(2, null)])),
    'GET /api/me/liked': () => json(200, liked()),
    'GET /api/me/liked/items': () => json(200, page([likedItem(3)])),
    'GET /api/me/watch-later': () => json(200, WATCH_LATER),
    [`GET /api/playlists/${WATCH_LATER.id}/items`]: () =>
      json(200, page(lists.watchLater ?? [item(4)])),
  })
}

const shelf = (name: string) => within(screen.getByRole('region', { name }))

describe('YouPage', () => {
  it('shows the viewer’s channel and a shelf of each list', async () => {
    mockYou()
    renderApp('/feed/you')

    expect(await screen.findByRole('heading', { level: 1, name: ANNA.handle })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View channel' })).toHaveAttribute(
      'href',
      `/@${ANNA.handle}`,
    )
    expect(await shelf('History').findByText(summary(1).title)).toBeInTheDocument()
    expect(await shelf('Playlists').findByText('Liked videos')).toBeInTheDocument()
    expect(shelf('Playlists').getByText('Watch later')).toBeInTheDocument()
    expect(shelf('Playlists').getAllByText(/^Private • Playlist$/)).toHaveLength(3)
    expect(await shelf('Watch later').findByText(summary(4).title)).toBeInTheDocument()
    expect(await shelf('Liked videos').findByText(summary(3).title)).toBeInTheDocument()
    const viewAll = ['History', 'Playlists', 'Watch later', 'Liked videos'].map((name) =>
      shelf(name).getByRole('link', { name: 'View all' }).getAttribute('href'),
    )
    expect(viewAll).toEqual([
      '/feed/history',
      '/feed/playlists',
      '/playlist?list=WL',
      '/playlist?list=LL',
    ])
  })

  it('leaves out an empty shelf', async () => {
    mockYou({ history: [], watchLater: [] })
    renderApp('/feed/you')

    const likedVideos = within(await screen.findByRole('region', { name: 'Liked videos' }))
    expect(await likedVideos.findByText(summary(3).title)).toBeInTheDocument()
    expect(await shelf('Playlists').findByText('Liked videos')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'History' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Watch later' })).not.toBeInTheDocument()
  })

  it('asks a guest to sign in', async () => {
    mockApi({ 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) })
    renderApp('/feed/you')

    expect(
      await screen.findByRole('heading', { name: 'Enjoy your favorite videos' }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Sign in' }).length).toBeGreaterThan(0)
  })

  it('is where You in the guide leads', async () => {
    mockYou()
    renderApp('/feed/you')

    const guide = within(await screen.findByRole('navigation', { name: 'Main' }))
    expect(await guide.findByRole('link', { name: 'You' })).toHaveAttribute('href', '/feed/you')
  })
})
