import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ANNA, json, mockApi } from '../../test/api'
import { channel } from '../../test/channels'
import { liked, likedItem } from '../../test/liked'
import { intersectAll } from '../../test/observers'
import { item, playlist } from '../../test/playlists'
import { renderApp } from '../../test/render'
import { setScreenWidth } from '../../test/screen'
import { detail, page, summary } from '../../test/videos'

const SIGNED_IN = { 'GET /api/auth/me': () => json(200, ANNA) }
const GUEST = { 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) }
const PLAYLIST = playlist(1, { title: 'Blender films', visibility: 'public', video_count: 3 })
const API = `/api/playlists/${PLAYLIST.id}`
const WATCH_LATER = playlist(9, { title: 'Watch later', kind: 'watch_later', video_count: 3 })
/** Up next of every video: one that isn't in the list. */
const UP_NEXT = summary(8)

type Handlers = Parameters<typeof mockApi>[0]

/** Enough of video `n`'s watch page for it to load and play. */
function watchApi(n: number): Handlers {
  const id = summary(n).id
  const base = `/api/videos/${id}`
  return {
    [`GET ${base}`]: () => json(200, detail(n)),
    [`GET ${base}/saved`]: () => json(200, { saved: false }),
    [`GET ${base}/related`]: () => json(200, page([UP_NEXT])),
    [`GET ${base}/comments`]: () => json(200, page([])),
    [`POST ${base}/views/start`]: () => json(204),
    [`PUT /api/me/history/${id}`]: () => json(204),
  }
}

/** Videos 1–3 in Blender films; `more` adds or replaces routes. */
function mockQueue(more: Handlers = {}, viewer: Handlers = SIGNED_IN) {
  return mockApi({
    ...viewer,
    'GET /api/channels/openmovieclub': () => json(200, channel()),
    'GET /api/me/history/progress': () => json(200, {}),
    'GET /api/me/history/settings': () => json(200, { paused: false }),
    ...[1, 2, 3, 8].reduce((all, n) => ({ ...all, ...watchApi(n) }), {}),
    [`GET ${API}`]: () => json(200, PLAYLIST),
    [`GET ${API}/items`]: () => json(200, page([item(1), item(2), item(3)])),
    ...more,
  })
}

async function openPanel(path: string, name = 'Blender films') {
  const router = renderApp(path)
  return { router, panel: await screen.findByRole('region', { name }) }
}

function location(router: ReturnType<typeof renderApp>) {
  return router.state.location.search
}

describe('WatchPage with a list', () => {
  it('shows the list above Up next, the current video marked', async () => {
    mockQueue()
    const { panel } = await openPanel(`/watch?v=video-00002&list=${PLAYLIST.id}`)

    expect(within(panel).getByRole('link', { name: 'Blender films' })).toHaveAttribute(
      'href',
      `/playlist?list=${PLAYLIST.id}`,
    )
    expect(panel).toHaveTextContent('Open Movie Club • 2 / 3')
    expect(within(panel).getByRole('link', { current: true })).toHaveTextContent('Video 2')
    expect(within(panel).getByRole('link', { name: /Video 3/ })).toHaveAttribute(
      'href',
      `/watch?v=video-00003&list=${PLAYLIST.id}`,
    )
    const upNext = await screen.findByRole('region', { name: 'Up next' })
    expect(panel.compareDocumentPosition(upNext)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  })

  it('goes to the list’s next video with Next and Shift+N', async () => {
    const user = userEvent.setup()
    mockQueue()
    const { router } = await openPanel(`/watch?v=video-00001&list=${PLAYLIST.id}`)

    await user.click(await screen.findByRole('button', { name: 'Next' }))
    expect(location(router)).toBe(`?v=video-00002&list=${PLAYLIST.id}`)
    await screen.findByRole('heading', { level: 1, name: 'Video 2' })
    await user.keyboard('{Shift>}N{/Shift}')
    expect(location(router)).toBe(`?v=video-00003&list=${PLAYLIST.id}`)
  })

  it('plays the next video when one ends, and stops after the last', async () => {
    const user = userEvent.setup()
    mockQueue()
    const { router } = await openPanel(`/watch?v=video-00002&list=${PLAYLIST.id}`)
    await screen.findByRole('region', { name: 'Video player' })

    fireEvent.ended(document.querySelector('video')!)
    await waitFor(() => expect(location(router)).toBe(`?v=video-00003&list=${PLAYLIST.id}`))
    await screen.findByRole('heading', { level: 1, name: 'Video 3' })
    await screen.findByRole('region', { name: 'Video player' })
    fireEvent.ended(document.querySelector('video')!)
    expect(location(router)).toBe(`?v=video-00003&list=${PLAYLIST.id}`)

    // After the list, Next leaves it for Up next.
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(location(router)).toBe(`?v=${UP_NEXT.id}`)
  })

  it('loads pages until it finds the current video', async () => {
    const fetch = mockQueue({
      [`GET ${API}/items`]: (request) =>
        new URL(request.url).searchParams.get('cursor') === 'two'
          ? json(200, page([item(3)]))
          : json(200, page([item(1), item(2)], 'two')),
    })
    const { panel } = await openPanel(`/watch?v=video-00003&list=${PLAYLIST.id}`)

    await waitFor(() => expect(panel).toHaveTextContent('Open Movie Club • 3 / 3'))
    expect(within(panel).getByRole('link', { current: true })).toHaveTextContent('Video 3')
    const pages = fetch.mock.calls.filter(([request]) => request.url.includes('/items'))
    expect(pages).toHaveLength(2)
  })

  it('loads more rows as the panel scrolls, counting the list until then', async () => {
    mockQueue({
      [`GET ${API}/items`]: (request) =>
        new URL(request.url).searchParams.get('cursor') === 'two'
          ? json(200, page([item(3)]))
          : json(200, page([item(1), item(2)], 'two')),
    })
    const { panel } = await openPanel(`/watch?v=video-00001&list=${PLAYLIST.id}`)
    expect(panel).toHaveTextContent('Open Movie Club • 1 / 3')
    expect(within(panel).queryByRole('link', { name: /Video 3/ })).not.toBeInTheDocument()

    act(() => intersectAll())

    expect(await within(panel).findByRole('link', { name: /Video 3/ })).toBeInTheDocument()
  })

  it('plays the viewer’s Liked videos', async () => {
    mockQueue({
      'GET /api/me/liked': () => json(200, liked()),
      'GET /api/me/liked/items': () => json(200, page([likedItem(1), likedItem(2)])),
    })
    const { panel } = await openPanel('/watch?v=video-00001&list=LL', 'Liked videos')

    expect(within(panel).getByRole('link', { name: 'Liked videos' })).toHaveAttribute(
      'href',
      '/playlist?list=LL',
    )
    expect(panel).toHaveTextContent(`${ANNA.handle} • 1 / 2`)
    expect(within(panel).getByRole('link', { name: /Video 2/ })).toHaveAttribute(
      'href',
      '/watch?v=video-00002&list=LL',
    )
  })

  it('plays the viewer’s Watch later', async () => {
    const user = userEvent.setup()
    mockQueue({
      'GET /api/me/watch-later': () => json(200, WATCH_LATER),
      [`GET /api/playlists/${WATCH_LATER.id}/items`]: () => json(200, page([item(1), item(2)])),
    })
    const { router, panel } = await openPanel('/watch?v=video-00001&list=WL', 'Watch later')

    expect(within(panel).getByRole('link', { name: 'Watch later' })).toHaveAttribute(
      'href',
      '/playlist?list=WL',
    )
    await user.click(await screen.findByRole('button', { name: 'Next' }))
    expect(location(router)).toBe('?v=video-00002&list=WL')
  })

  it.each([
    ['a guest’s Liked videos', 'LL', GUEST, {}],
    ['a list that isn’t one', 'nope', SIGNED_IN, {}],
    [
      'a playlist that is gone or private',
      PLAYLIST.id,
      SIGNED_IN,
      { [`GET ${API}`]: () => json(404, { detail: 'Playlist not found' }) },
    ],
  ])('plays the video alone for %s', async (_, list, viewer, more) => {
    const user = userEvent.setup()
    const fetch = mockQueue(more, viewer)
    const router = renderApp(`/watch?v=video-00001&list=${list}`)

    // Next is there once the page knows there is no list to go through.
    await user.click(await screen.findByRole('button', { name: 'Next' }))
    expect(location(router)).toBe(`?v=${UP_NEXT.id}`)
    expect(screen.queryByRole('region', { name: /Blender films|Liked videos/ })).toBeNull()
    const urls = fetch.mock.calls.map(([request]) => new URL(request.url).pathname)
    expect(urls.filter((url) => url.startsWith('/api/me/liked'))).toEqual([])
  })

  it('puts the list before Up next on narrow screens', async () => {
    setScreenWidth(900)
    mockQueue()
    const { panel } = await openPanel(`/watch?v=video-00001&list=${PLAYLIST.id}`)

    const upNext = await screen.findByRole('region', { name: 'Up next' })
    expect(panel.compareDocumentPosition(upNext)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
    expect(upNext.parentElement).toBe(panel.parentElement)
  })
})
