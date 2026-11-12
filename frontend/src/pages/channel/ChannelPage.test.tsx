import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import type { Channel } from '../../channels/types'
import { ANNA, json, mockApi } from '../../test/api'
import { channel } from '../../test/channels'
import { intersectAll } from '../../test/observers'
import { playlist } from '../../test/playlists'
import { renderApp } from '../../test/render'
import { page, summary } from '../../test/videos'

const SIGNED_IN = { 'GET /api/auth/me': () => json(200, ANNA) }
const GUEST = { 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) }
const API = '/api/channels/openmovieclub'

/** The channel API; subscribe and unsubscribe answer like the server. */
function mockChannel(data: Channel = channel(), viewer = SIGNED_IN) {
  const answer = (subscribed: boolean) => () =>
    json(200, {
      subscriber_count:
        data.subscriber_count + (subscribed === data.is_subscribed ? 0 : subscribed ? 1 : -1),
      is_subscribed: subscribed,
    })
  return mockApi({
    ...viewer,
    [`GET ${API}`]: () => json(200, data),
    [`GET ${API}/videos`]: () => json(200, page([summary(1)])),
    [`PUT ${API}/subscription`]: answer(true),
    [`DELETE ${API}/subscription`]: answer(false),
  })
}

const queryOf = (request: Request) => Object.fromEntries(new URL(request.url).searchParams)

async function openChannel(path = '/@openmovieclub') {
  renderApp(path)
  return screen.findByRole('heading', { level: 1, name: 'Open Movie Club' })
}

describe('ChannelPage', () => {
  it('shows the channel header', async () => {
    mockChannel()
    await openChannel()

    expect(screen.getByText('@openmovieclub')).toBeInTheDocument()
    expect(screen.getByText(/2 subscribers • 3 videos/)).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: 'Subscribe' })).toBeEnabled()
    expect(document.title).toBe('Open Movie Club - ViTube')
    expect(screen.queryByRole('note')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /More actions/ })).not.toBeInTheDocument()
  })

  it('lets an admin terminate the channel from its page', async () => {
    let terminated = false
    const fetch = mockApi({
      'GET /api/auth/me': () => json(200, { ...ANNA, role: 'admin' }),
      [`GET ${API}`]: () => json(200, channel({ is_terminated: terminated })),
      [`GET ${API}/videos`]: () => json(200, page([])),
      'PUT /api/moderation/users/openmovieclub/status': () => {
        terminated = true
        return json(204)
      },
    })
    await openChannel()

    await userEvent.click(
      await screen.findByRole('button', { name: 'More actions for @openmovieclub' }),
    )
    await userEvent.click(screen.getByRole('menuitem', { name: 'Restrict @openmovieclub' }))
    const dialog = within(screen.getByRole('dialog', { name: 'Restrict account' }))
    await userEvent.click(dialog.getByRole('radio', { name: /^Terminate channel/ }))
    await userEvent.click(dialog.getByRole('button', { name: 'Terminate' }))

    expect(await screen.findByRole('note')).toHaveTextContent('Channel terminated')
    expect(screen.getByRole('status')).toHaveTextContent('@openmovieclub’s channel terminated')
    expect(screen.queryByRole('button', { name: 'Subscribe' })).not.toBeInTheDocument()
    const call = fetch.mock.calls.find(([request]) => request.method === 'PUT')
    expect(await call?.[0].json()).toEqual({ status: 'terminated', reason: '' })
  })

  it('tells a moderator a terminated channel is frozen and offers no Subscribe', async () => {
    mockChannel(channel({ is_terminated: true, video_count: 0 }))
    await openChannel()

    const notice = screen.getByRole('note')
    expect(notice).toHaveTextContent('Channel terminated')
    expect(notice).toHaveTextContent('Only moderators can see this channel.')
    await screen.findByRole('button', { name: 'Account menu' }) // the viewer is known
    expect(screen.queryByRole('button', { name: 'Subscribe' })).not.toBeInTheDocument()
  })

  it('accepts the handle in any case and shows it as stored', async () => {
    mockApi({
      ...GUEST,
      'GET /api/channels/OpenMovieClub': () => json(200, channel()),
      'GET /api/channels/OpenMovieClub/videos': () => json(200, page([])),
    })
    await openChannel('/@OpenMovieClub')

    expect(screen.getByText('@openmovieclub')).toBeInTheDocument()
  })

  it('subscribes at once and keeps the server’s count', async () => {
    const fetch = mockChannel()
    await openChannel()

    await userEvent.click(await screen.findByRole('button', { name: 'Subscribe' }))

    expect(await screen.findByRole('button', { name: /Subscribed/ })).toBeInTheDocument()
    expect(screen.getByText(/3 subscribers/)).toBeInTheDocument()
    expect(fetch.mock.calls.some(([request]) => request.method === 'PUT')).toBe(true)
  })

  it('unsubscribes from the Subscribed menu after the confirm dialog', async () => {
    mockChannel(channel({ is_subscribed: true, subscriber_count: 3 }))
    await openChannel()

    await userEvent.click(await screen.findByRole('button', { name: /Subscribed/ }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('menuitem', { name: 'Unsubscribe' }))
    const dialog = screen.getByRole('dialog', { name: 'Unsubscribe' })
    expect(within(dialog).getByText('Unsubscribe from Open Movie Club?')).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Unsubscribe' }))

    expect(await screen.findByRole('button', { name: 'Subscribe' })).toBeInTheDocument()
    expect(screen.getByText(/2 subscribers/)).toBeInTheDocument()
  })

  it('rolls back when the request fails', async () => {
    mockApi({
      ...SIGNED_IN,
      [`GET ${API}`]: () => json(200, channel()),
      [`GET ${API}/videos`]: () => json(200, page([])),
      [`PUT ${API}/subscription`]: () => json(503, { detail: 'Try again later' }),
    })
    await openChannel()

    await userEvent.click(await screen.findByRole('button', { name: 'Subscribe' }))

    await waitFor(() => expect(screen.getByRole('button', { name: 'Subscribe' })).toBeEnabled())
    expect(screen.getByText(/2 subscribers/)).toBeInTheDocument()
  })

  it('asks a guest to sign in', async () => {
    mockChannel(channel(), GUEST)
    await openChannel()

    await userEvent.click(await screen.findByRole('button', { name: 'Subscribe' }))

    expect(screen.getByText('Want to subscribe to this channel?')).toBeInTheDocument()
    const card = screen.getByRole('dialog', { name: 'Want to subscribe to this channel?' })
    expect(within(card).getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
  })

  it('shows Manage videos instead of Subscribe on your own channel', async () => {
    const own = channel({ handle: ANNA.handle, name: ANNA.handle })
    mockApi({
      ...SIGNED_IN,
      [`GET /api/channels/${ANNA.handle}`]: () => json(200, own),
      [`GET /api/channels/${ANNA.handle}/videos`]: () => json(200, page([])),
    })
    renderApp(`/@${ANNA.handle}`)
    await screen.findByRole('heading', { level: 1, name: ANNA.handle })

    await screen.findByRole('button', { name: 'Account menu' }) // the viewer is known
    expect(screen.queryByRole('button', { name: /Subscribe/ })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Manage videos' })).toHaveAttribute(
      'href',
      '/studio/videos',
    )
  })

  it('shows Manage videos to no one but the owner', async () => {
    mockChannel()
    await openChannel()

    expect(await screen.findByRole('button', { name: 'Subscribe' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Manage videos' })).not.toBeInTheDocument()
  })

  it('shows "not available" for an unknown channel', async () => {
    const notFound = () => json(404, { detail: 'Channel not found' })
    mockApi({ ...GUEST, [`GET ${API}`]: notFound, [`GET ${API}/videos`]: notFound })
    renderApp('/@openmovieclub')

    expect(await screen.findByText(/This page isn.t available/)).toBeInTheDocument()
  })

  it.each(['/openmovieclub', '/@ab', '/@a b'])('treats %s as an unknown page', async (path) => {
    const fetch = mockApi(GUEST)
    renderApp(path)

    expect(await screen.findByText(/This page isn.t available/)).toBeInTheDocument()
    const urls = fetch.mock.calls.map(([request]) => new URL(request.url).pathname)
    expect(urls.filter((url) => url.startsWith('/api/channels'))).toEqual([])
  })

  describe('Videos tab', () => {
    it('lists the channel’s videos without repeating the channel', async () => {
      mockChannel()
      await openChannel()

      const card = (await screen.findByRole('link', { name: 'Video 1' })).closest('article')!
      expect(within(card).queryByText('Open Movie Club')).not.toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Videos' })).toHaveAttribute('aria-current', 'page')
      expect(screen.getByRole('link', { name: 'Videos' })).toHaveAttribute(
        'href',
        '/@openmovieclub/videos',
      )
    })

    it('is the same at /@handle/videos', async () => {
      mockChannel()
      await openChannel('/@openmovieclub/videos')

      expect(await screen.findByRole('link', { name: 'Video 1' })).toBeInTheDocument()
    })

    it('sorts by the chosen chip', async () => {
      const fetch = mockApi({
        ...GUEST,
        [`GET ${API}`]: () => json(200, channel()),
        [`GET ${API}/videos`]: (request) =>
          json(200, page([summary(queryOf(request).sort === 'popular' ? 2 : 1)])),
      })
      await openChannel()
      expect(await screen.findByRole('link', { name: 'Video 1' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Latest' })).toHaveAttribute('aria-pressed', 'true')

      await userEvent.click(screen.getByRole('button', { name: 'Popular' }))

      expect(await screen.findByRole('link', { name: 'Video 2' })).toBeInTheDocument()
      expect(screen.queryByRole('link', { name: 'Video 1' })).not.toBeInTheDocument()
      const sorts = fetch.mock.calls
        .filter(([request]) => request.url.includes('/videos'))
        .map(([request]) => queryOf(request).sort)
      expect(sorts).toEqual(['latest', 'popular'])
    })

    it('loads the next page on scroll', async () => {
      const fetch = mockApi({
        ...GUEST,
        [`GET ${API}`]: () => json(200, channel()),
        [`GET ${API}/videos`]: (request) =>
          queryOf(request).cursor === 'next'
            ? json(200, page([summary(2)]))
            : json(200, page([summary(1)], 'next')),
      })
      await openChannel()
      await screen.findByRole('link', { name: 'Video 1' })

      act(() => intersectAll())

      expect(await screen.findByRole('link', { name: 'Video 2' })).toBeInTheDocument()
      const cursors = fetch.mock.calls
        .filter(([request]) => request.url.includes('/videos'))
        .map(([request]) => queryOf(request).cursor)
      expect(cursors).toEqual([undefined, 'next'])
    })

    it('says so when the channel has no videos', async () => {
      mockApi({
        ...GUEST,
        [`GET ${API}`]: () => json(200, channel({ video_count: 0 })),
        [`GET ${API}/videos`]: () => json(200, page([])),
      })
      await openChannel()

      expect(
        await screen.findByRole('heading', { name: 'This channel doesn’t have any content' }),
      ).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Latest' })).not.toBeInTheDocument()
    })
  })

  describe('Playlists tab', () => {
    it('shows the channel’s playlists as cards that open them', async () => {
      const films = playlist(1, {
        title: 'Blender films',
        visibility: 'public',
        video_count: 3,
        thumbnail_url: '/media/thumbs/1.jpg',
      })
      mockApi({
        ...GUEST,
        [`GET ${API}`]: () => json(200, channel()),
        [`GET ${API}/playlists`]: () => json(200, page([films])),
      })
      await openChannel('/@openmovieclub/playlists')

      const title = await screen.findByRole('link', { name: 'Blender films' })
      expect(title).toHaveAttribute('href', `/playlist?list=${films.id}`)
      const card = title.closest('article')!
      expect(within(card).getByText('3 videos')).toBeInTheDocument()
      expect(within(card).getByRole('link', { name: 'View full playlist' })).toHaveAttribute(
        'href',
        `/playlist?list=${films.id}`,
      )
      expect(screen.getByRole('link', { name: 'Playlists' })).toHaveAttribute(
        'aria-current',
        'page',
      )
    })

    it('loads the next page on scroll', async () => {
      mockApi({
        ...GUEST,
        [`GET ${API}`]: () => json(200, channel()),
        [`GET ${API}/playlists`]: (request) =>
          queryOf(request).cursor === 'next'
            ? json(200, page([playlist(2, { visibility: 'public' })]))
            : json(200, page([playlist(1, { visibility: 'public' })], 'next')),
      })
      await openChannel('/@openmovieclub/playlists')
      await screen.findByRole('link', { name: 'Playlist 1' })

      act(() => intersectAll())

      expect(await screen.findByRole('link', { name: 'Playlist 2' })).toBeInTheDocument()
    })

    it('says so when the channel has no playlists', async () => {
      mockApi({
        ...GUEST,
        [`GET ${API}`]: () => json(200, channel()),
        [`GET ${API}/playlists`]: () => json(200, page([])),
      })
      await openChannel('/@openmovieclub/playlists')

      expect(
        await screen.findByRole('heading', { name: 'This channel has no playlists.' }),
      ).toBeInTheDocument()
    })
  })
})
