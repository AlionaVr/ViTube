import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ANNA, json, mockApi } from '../../test/api'
import { channel } from '../../test/channels'
import { shuffled } from '../../playlists/queue'
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

/** Ends the video and lets a navigation it starts run, so a test sees where it leads. */
async function endVideo() {
  fireEvent.ended(document.querySelector('video')!)
  await act(async () => {})
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
    expect(within(panel).getByRole('link', { name: 'Open Movie Club' })).toHaveAttribute(
      'href',
      '/@openmovieclub',
    )
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

    await endVideo()
    expect(location(router)).toBe(`?v=video-00003&list=${PLAYLIST.id}`)
    await screen.findByRole('heading', { level: 1, name: 'Video 3' })
    await screen.findByRole('region', { name: 'Video player' })
    await endVideo()
    expect(location(router)).toBe(`?v=video-00003&list=${PLAYLIST.id}`)
    expect(screen.getByRole('heading', { level: 1, name: 'Video 3' })).toBeInTheDocument()

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

  it('shuffles from the panel: the video plays on and comes first', async () => {
    const user = userEvent.setup()
    mockQueue()
    const { router, panel } = await openPanel(`/watch?v=video-00002&list=${PLAYLIST.id}`)
    await screen.findByRole('region', { name: 'Video player' })
    const playing = document.querySelector('video')

    await user.click(
      within(panel).getByRole('button', { name: 'Shuffle playlist', pressed: false }),
    )

    expect(screen.getByRole('status')).toHaveTextContent('Shuffle on')
    const params = new URLSearchParams(location(router))
    const seed = params.get('shuffle')!
    expect([params.get('v'), params.get('list'), params.get('index')]).toEqual([
      'video-00002',
      PLAYLIST.id,
      '1',
    ])
    expect(
      within(panel).getByRole('button', { name: 'Shuffle playlist', pressed: true }),
    ).toBeVisible()
    expect(document.querySelector('video')).toBe(playing)
    expect(panel).toHaveTextContent('Open Movie Club • 1 / 3')
    const rows = within(panel).getAllByRole('link', { name: /Video/ })
    expect(rows[0]).toHaveAttribute('aria-current', 'true')
    expect(rows[0]).toHaveTextContent('Video 2')

    // Next goes to the second row, in the same shuffle.
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(`/watch${location(router)}`).toBe(rows[1].getAttribute('href'))
    expect(new URLSearchParams(location(router)).get('index')).toBe('2')
    expect(new URLSearchParams(location(router)).get('shuffle')).toBe(seed)

    await user.click(within(panel).getByRole('button', { name: 'Shuffle playlist', pressed: true }))
    expect(location(router)).not.toMatch(/shuffle|index/)
    expect(screen.getByRole('status')).toHaveTextContent('Shuffle off')
  })

  it('scrolls the panel to the current row again when the shuffle moves it', async () => {
    const user = userEvent.setup()
    mockQueue()
    const { panel } = await openPanel(`/watch?v=video-00002&list=${PLAYLIST.id}`)
    const scrolled = vi.spyOn(Element.prototype, 'scrollTop', 'set')

    await user.click(within(panel).getByRole('button', { name: 'Shuffle playlist' }))

    expect(scrolled).toHaveBeenCalled()
  })

  it('lets the panel end where the player does', async () => {
    vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockReturnValue(540)
    vi.stubGlobal(
      'ResizeObserver',
      // Reports a size at once, as a browser does after the first layout.
      class {
        private readonly changed: () => void
        constructor(changed: () => void) {
          this.changed = changed
        }
        observe() {
          this.changed()
        }
        disconnect() {}
      },
    )
    mockQueue()
    const { panel } = await openPanel(`/watch?v=video-00002&list=${PLAYLIST.id}`)

    const page = panel.closest<HTMLElement>('[style]')!
    expect(page.style.getPropertyValue('--player-height')).toBe('540px')
  })

  it('goes through a shuffled list in its order and stops at its end', async () => {
    const user = userEvent.setup()
    mockQueue()
    const order = shuffled(
      [1, 2, 3].map((n) => summary(n)),
      'seed-a',
    ).map((video) => video.id)
    const at = (index: number) =>
      `?v=${order[index - 1]}&list=${PLAYLIST.id}&shuffle=seed-a&index=${index}`
    const { router, panel } = await openPanel(`/watch${at(1)}`)

    expect(
      within(panel)
        .getAllByRole('heading', { level: 3 })
        .map((title) => title.textContent),
    ).toEqual(order.map((id) => `Video ${Number(id.slice(-1))}`))
    await user.click(await screen.findByRole('button', { name: 'Next' }))
    expect(location(router)).toBe(at(2))
    await screen.findByRole('heading', { level: 1, name: `Video ${Number(order[1].slice(-1))}` })
    await user.click(
      within(panel).getByRole('link', { name: new RegExp(`Video ${order[2].slice(-1)}`) }),
    )
    expect(location(router)).toBe(at(3))
    await screen.findByRole('region', { name: 'Video player' })

    await endVideo()
    expect(location(router)).toBe(at(3))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(location(router)).toBe(`?v=${UP_NEXT.id}`)
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

/** Ends the video as a browser does: `ended` is set, so the player shows its end screen. */
function playToTheEnd() {
  const video = document.querySelector('video')!
  Object.defineProperty(video, 'ended', { configurable: true, value: true })
  fireEvent.ended(video)
}

describe('WatchPage without a list', () => {
  afterEach(() => localStorage.clear())

  it('counts down to Up next’s first video at the end, Autoplay being on by default', async () => {
    mockQueue()
    const router = renderApp('/watch?v=video-00002')
    await screen.findByRole('region', { name: 'Video player' })
    expect(await screen.findByRole('switch', { name: 'Autoplay' })).toBeChecked()

    playToTheEnd()
    const countdown = await screen.findByRole('region', { name: 'Autoplay countdown' })
    expect(countdown).toHaveTextContent(UP_NEXT.title)
    await userEvent.click(within(countdown).getByRole('button', { name: 'Play now' }))

    expect(location(router)).toBe(`?v=${UP_NEXT.id}`)
  })

  it('stays at the end with Autoplay off, and keeps the choice', async () => {
    mockQueue()
    renderApp('/watch?v=video-00002')
    await userEvent.click(await screen.findByRole('switch', { name: 'Autoplay' }))

    playToTheEnd()

    expect(screen.queryByRole('region', { name: 'Autoplay countdown' })).not.toBeInTheDocument()
    expect(localStorage.getItem('vitube:autoplay')).toBe('0')
  })
})
