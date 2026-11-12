import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import type { Playlist, PlaylistItem } from '../../playlists/types'

import { ANNA, json, mockApi } from '../../test/api'
import { liked, likedItem } from '../../test/liked'
import { intersectAll } from '../../test/observers'
import { item, mine, playlist } from '../../test/playlists'
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
const SIGNED_IN = {
  'GET /api/auth/me': () => json(200, ANNA),
  'GET /api/me/subscriptions': () => json(200, page([])),
}
const ANNAS = playlist(2, {
  title: 'Blender films',
  video_count: 3,
  owner: { handle: ANNA.handle, name: ANNA.handle, avatar_url: null },
})
const OWN = `/api/playlists/${ANNAS.id}`
const WATCH_LATER = playlist(9, {
  title: 'Watch later',
  kind: 'watch_later',
  video_count: 1,
  owner: { handle: ANNA.handle, name: ANNA.handle, avatar_url: null },
})

type Handlers = Parameters<typeof mockApi>[0]

/** Anna's playlist as a server that keeps changes: edits, removals and moves. */
function mockOwn(fail: Partial<Record<'PATCH' | 'DELETE', boolean>> = {}, more: Handlers = {}) {
  let current: Playlist = ANNAS
  let items: PlaylistItem[] = [item(1), item(2), item(3)]
  const sent: { method: string; path: string; body?: unknown }[] = []
  const at = (request: Request) => new URL(request.url).pathname.split('/').at(-1) ?? ''
  const fetch = mockApi({
    ...SIGNED_IN,
    [`GET ${OWN}`]: () => json(200, current),
    [`GET ${OWN}/items`]: () => json(200, page(items)),
    [`PATCH ${OWN}`]: async (request) => {
      const body = (await request.json()) as Partial<Playlist>
      sent.push({ method: 'PATCH', path: OWN, body })
      if (fail.PATCH) return json(422, { detail: [{ msg: 'String should match pattern' }] })
      current = { ...current, ...body }
      return json(200, current)
    },
    [`DELETE ${OWN}`]: () => {
      sent.push({ method: 'DELETE', path: OWN })
      return json(204)
    },
    ...Object.fromEntries(
      [1, 2, 3].flatMap((n) => {
        const path = `${OWN}/items/video-0000${n}`
        return [
          [
            `DELETE ${path}`,
            (request: Request) => {
              sent.push({ method: 'DELETE', path })
              if (fail.DELETE) return json(500)
              items = items.filter((i) => i.video.id !== at(request))
              return json(204)
            },
          ],
          [
            `PATCH ${path}`,
            async (request: Request) => {
              const body = (await request.json()) as { before: string | null }
              sent.push({ method: 'PATCH', path, body })
              if (fail.PATCH) return json(500)
              const moving = items.find((i) => i.video.id === at(request))!
              const rest = items.filter((i) => i !== moving)
              const index = body.before ? rest.findIndex((i) => i.video.id === body.before) : -1
              items = index < 0 ? [...rest, moving] : rest.toSpliced(index, 0, moving)
              return json(204)
            },
          ],
        ]
      }),
    ),
    // The Playlists page, where deleting leads.
    'GET /api/me/playlists': () => json(200, page([playlist(9, { kind: 'watch_later' })])),
    'GET /api/me/liked': () => json(200, liked()),
    ...more,
  })
  return { fetch, sent }
}

async function rowTitles() {
  const list = await screen.findByRole('list', { name: '' })
  return within(list)
    .getAllByRole('heading')
    .map((heading) => heading.textContent)
}

/** Opens a row's ⋮ and names its choices. */
async function menuOf(row: number) {
  const user = userEvent.setup()
  const rows = within(await screen.findByRole('list', { name: '' })).getAllByRole('listitem')
  await user.click(within(rows[row]).getByRole('button', { name: 'Action menu' }))
  return screen.getAllByRole('menuitem').map((choice) => choice.textContent)
}

async function choose(row: number, choice: string) {
  const user = userEvent.setup()
  const rows = within(await screen.findByRole('list', { name: '' })).getAllByRole('listitem')
  await user.click(within(rows[row]).getByRole('button', { name: 'Action menu' }))
  await user.click(screen.getByRole('menuitem', { name: choice }))
}

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
    // Played as a list, as on YouTube: the watch page shows it and goes through it.
    expect(within(rows[1]).getByRole('link', { name: /Video 2/ })).toHaveAttribute(
      'href',
      `/watch?v=video-00002&list=${PLAYLIST.id}`,
    )
    expect(screen.getByRole('link', { name: /Play all/ })).toHaveAttribute(
      'href',
      `/watch?v=video-00001&list=${PLAYLIST.id}`,
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

  it('lets a guest only share a video, from its ⋮', async () => {
    const user = userEvent.setup()
    mockApi({
      ...GUEST,
      [`GET ${API}`]: () => json(200, { ...PLAYLIST, visibility: 'public' }),
      [`GET ${API}/items`]: () => json(200, page([item(1), item(2)])),
    })
    renderApp(`/playlist?list=${PLAYLIST.id}`)

    expect(await menuOf(1)).toEqual(['Share'])
    await user.click(screen.getByRole('menuitem', { name: 'Share' }))

    const dialog = screen.getByRole('dialog', { name: 'Share' })
    expect(within(dialog).getByRole('textbox', { name: 'Video link' })).toHaveValue(
      `${window.location.origin}/watch?v=video-00002`,
    )
  })

  describe('saving from ⋮', () => {
    /** Someone else's public playlist; `saved`: how the Watch later request answers. */
    function mockOthers(saved = () => json(204)) {
      const sent: string[] = []
      mockApi({
        ...SIGNED_IN,
        [`GET ${API}`]: () => json(200, { ...PLAYLIST, visibility: 'public' }),
        [`GET ${API}/items`]: () => json(200, page([item(1), item(2)])),
        'GET /api/me/watch-later': () => json(200, WATCH_LATER),
        [`PUT /api/playlists/${WATCH_LATER.id}/items/video-00002`]: (request) => {
          sent.push(new URL(request.url).pathname)
          return saved()
        },
        'GET /api/me/playlists': () => json(200, page([mine(9, false, WATCH_LATER)])),
      })
      return { sent }
    }

    it('offers a signed-in viewer save and share on others’ videos', async () => {
      mockOthers()
      renderApp(`/playlist?list=${PLAYLIST.id}`)

      expect(await menuOf(0)).toEqual(['Save to Watch later', 'Save to playlist', 'Share'])
    })

    it('saves a video to Watch later and says so', async () => {
      const { sent } = mockOthers()
      renderApp(`/playlist?list=${PLAYLIST.id}`)

      await choose(1, 'Save to Watch later')

      expect(await screen.findByRole('status')).toHaveTextContent('Saved to Watch later')
      expect(sent).toEqual([`/api/playlists/${WATCH_LATER.id}/items/video-00002`])
    })

    it('says so when saving to Watch later fails', async () => {
      mockOthers(() => json(500, { detail: 'Internal Server Error' }))
      renderApp(`/playlist?list=${PLAYLIST.id}`)

      await choose(1, 'Save to Watch later')

      expect(await screen.findByRole('status')).toHaveTextContent(
        'Couldn’t save the video. Try again.',
      )
    })

    it('opens the Save dialog for the row’s video', async () => {
      mockOthers()
      renderApp(`/playlist?list=${PLAYLIST.id}`)

      await choose(1, 'Save to playlist')

      const dialog = screen.getByRole('dialog', { name: 'Save video to...' })
      expect(await within(dialog).findByRole('checkbox', { name: /Watch later/ })).not.toBeChecked()
    })
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

  it.each(['/playlist', '/playlist?list=nope'])('needs a playlist id: %s', async (path) => {
    const fetch = mockApi(GUEST)
    renderApp(path)

    expect(await screen.findByText('The playlist does not exist.')).toBeInTheDocument()
    const urls = fetch.mock.calls.map(([request]) => new URL(request.url).pathname)
    expect(urls.filter((url) => url.startsWith('/api/playlists'))).toEqual([])
  })

  describe('owner', () => {
    it('edits the title, description and privacy', async () => {
      const user = userEvent.setup()
      const { sent } = mockOwn()
      renderApp(`/playlist?list=${ANNAS.id}`)

      await user.click(await screen.findByRole('button', { name: 'Edit playlist' }))
      const dialog = screen.getByRole('dialog', { name: 'Edit playlist' })
      const title = within(dialog).getByRole('textbox', { name: 'Title' })
      await user.clear(title)
      await user.type(title, 'Open movies')
      await user.type(within(dialog).getByRole('textbox', { name: 'Description' }), 'By Blender')
      await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Privacy' }), 'public')
      await user.click(within(dialog).getByRole('button', { name: 'Save' }))

      expect(sent).toEqual([
        {
          method: 'PATCH',
          path: OWN,
          body: { title: 'Open movies', description: 'By Blender', visibility: 'public' },
        },
      ])
      expect(
        await screen.findByRole('heading', { level: 1, name: 'Open movies' }),
      ).toBeInTheDocument()
      expect(screen.getByText('Public')).toBeInTheDocument()
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('keeps the edit open with the server’s reason when it fails', async () => {
      const user = userEvent.setup()
      mockOwn({ PATCH: true })
      renderApp(`/playlist?list=${ANNAS.id}`)

      await user.click(await screen.findByRole('button', { name: 'Edit playlist' }))
      await user.click(screen.getByRole('button', { name: 'Save' }))

      expect(await screen.findByRole('alert')).toHaveTextContent('String should match pattern')
      expect(screen.getByRole('dialog', { name: 'Edit playlist' })).toBeInTheDocument()
    })

    it('deletes the playlist after asking, then opens your playlists', async () => {
      const user = userEvent.setup()
      const { sent } = mockOwn()
      const router = renderApp(`/playlist?list=${ANNAS.id}`)

      await user.click(await screen.findByRole('button', { name: 'More actions' }))
      await user.click(screen.getByRole('menuitem', { name: 'Delete playlist' }))
      const dialog = screen.getByRole('dialog', { name: 'Delete playlist' })
      expect(dialog).toHaveTextContent('Are you sure you want to delete Blender films?')
      expect(sent).toEqual([])
      await user.click(within(dialog).getByRole('button', { name: 'Delete' }))

      await waitFor(() => expect(router.state.location.pathname).toBe('/feed/playlists'))
      expect(sent).toEqual([{ method: 'DELETE', path: OWN }])
      expect(screen.getByRole('status')).toHaveTextContent('Playlist deleted')
    })

    it('puts the owner’s actions after save and share', async () => {
      mockOwn()
      renderApp(`/playlist?list=${ANNAS.id}`)

      expect(await menuOf(1)).toEqual([
        'Save to Watch later',
        'Save to playlist',
        'Share',
        'Remove from Blender films',
        'Move to top',
        'Move to bottom',
      ])
    })

    it('keeps the Save dialog open when its video leaves the playlist', async () => {
      const user = userEvent.setup()
      const { sent } = mockOwn(
        {},
        { 'GET /api/me/playlists': () => json(200, page([mine(2, true, ANNAS)])) },
      )
      renderApp(`/playlist?list=${ANNAS.id}`)

      await choose(1, 'Save to playlist')
      const dialog = screen.getByRole('dialog', { name: 'Save video to...' })
      await user.click(await within(dialog).findByRole('checkbox', { name: /Blender films/ }))

      await waitFor(async () => expect(await rowTitles()).toEqual(['Video 1', 'Video 3']))
      expect(sent).toEqual([{ method: 'DELETE', path: `${OWN}/items/video-00002` }])
      expect(screen.getByRole('dialog', { name: 'Save video to...' })).toBe(dialog)
    })

    it('removes a video', async () => {
      const { sent } = mockOwn()
      renderApp(`/playlist?list=${ANNAS.id}`)

      await choose(1, 'Remove from Blender films')

      await waitFor(async () => expect(await rowTitles()).toEqual(['Video 1', 'Video 3']))
      expect(sent).toEqual([{ method: 'DELETE', path: `${OWN}/items/video-00002` }])
      expect(await screen.findByRole('status')).toHaveTextContent('Removed from Blender films')
    })

    it('moves a video to the top or the bottom', async () => {
      const { sent } = mockOwn()
      renderApp(`/playlist?list=${ANNAS.id}`)

      await choose(2, 'Move to top')
      await waitFor(async () =>
        expect(await rowTitles()).toEqual(['Video 3', 'Video 1', 'Video 2']),
      )
      await choose(1, 'Move to bottom')
      await waitFor(async () =>
        expect(await rowTitles()).toEqual(['Video 3', 'Video 2', 'Video 1']),
      )

      expect(sent.map((request) => request.body)).toEqual([
        { before: 'video-00001' },
        { before: null },
      ])
    })

    it('offers no move that changes nothing', async () => {
      const user = userEvent.setup()
      mockOwn()
      renderApp(`/playlist?list=${ANNAS.id}`)
      const rows = within(await screen.findByRole('list', { name: '' })).getAllByRole('listitem')

      await user.click(within(rows[0]).getByRole('button', { name: 'Action menu' }))
      expect(screen.queryByRole('menuitem', { name: 'Move to top' })).not.toBeInTheDocument()
      await user.keyboard('{Escape}')
      await user.click(within(rows[2]).getByRole('button', { name: 'Action menu' }))
      expect(screen.queryByRole('menuitem', { name: 'Move to bottom' })).not.toBeInTheDocument()
    })

    it('puts a failed move back and says so', async () => {
      mockOwn({ PATCH: true })
      renderApp(`/playlist?list=${ANNAS.id}`)

      await choose(2, 'Move to top')

      expect(await screen.findByRole('status')).toHaveTextContent(
        'Couldn’t change the playlist. Try again.',
      )
      expect(await rowTitles()).toEqual(['Video 1', 'Video 2', 'Video 3'])
    })

    it('gives others no owner tools', async () => {
      mockApi({
        ...SIGNED_IN,
        [`GET ${API}`]: () => json(200, { ...PLAYLIST, visibility: 'public' }),
        [`GET ${API}/items`]: () => json(200, page([item(1)])),
      })
      renderApp(`/playlist?list=${PLAYLIST.id}`)

      expect(await screen.findByRole('heading', { name: 'Video 1' })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Edit playlist' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'More actions' })).not.toBeInTheDocument()
      expect(await menuOf(0)).not.toContain('Remove from Blender films')
    })
  })

  describe('Watch later (list=WL)', () => {
    it('opens the viewer’s own Watch later', async () => {
      const watchLater = WATCH_LATER
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
      expect(screen.getByRole('link', { name: /Play all/ })).toHaveAttribute(
        'href',
        '/watch?v=video-00001&list=WL',
      )
      expect(screen.getByRole('link', { name: 'Watch later' })).toHaveAttribute(
        'aria-current',
        'page',
      )
      // Its own: videos have the menu, but it can't be edited or deleted.
      expect(screen.queryByRole('button', { name: 'Edit playlist' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'More actions' })).not.toBeInTheDocument()
      // Saving to Watch later is no choice on Watch later itself.
      expect(await menuOf(0)).toEqual(['Save to playlist', 'Share', 'Remove from Watch later'])
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

  describe('Liked videos (list=LL)', () => {
    function mockLiked(summary = liked(), items = [likedItem(1), likedItem(2)]) {
      return mockApi({
        ...SIGNED_IN,
        'GET /api/me/liked': () => json(200, summary),
        'GET /api/me/liked/items': () => json(200, page(items)),
      })
    }

    it('lists the viewer’s likes as a private playlist', async () => {
      mockLiked()
      renderApp('/playlist?list=LL')

      expect(
        await screen.findByRole('heading', { level: 1, name: 'Liked videos' }),
      ).toBeInTheDocument()
      expect(screen.getByText('Private')).toBeInTheDocument()
      expect(screen.getByText('2 videos')).toBeInTheDocument()
      expect(screen.getByText('Updated today')).toBeInTheDocument()
      const rows = within(screen.getByRole('region', { name: 'Videos' }))
      const titles = (await rows.findAllByRole('heading', { level: 3 })).map((h) => h.textContent)
      expect(titles).toEqual(['Video 1', 'Video 2'])
      expect(screen.getByRole('link', { name: /Play all/ })).toHaveAttribute(
        'href',
        '/watch?v=video-00001&list=LL',
      )
      expect(screen.getByRole('link', { name: 'Liked videos' })).toHaveAttribute(
        'aria-current',
        'page',
      )
      expect(document.title).toBe('Liked videos - ViTube')
      // Made from likes: nothing to edit or delete.
      expect(screen.queryByRole('button', { name: 'Edit playlist' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'More actions' })).not.toBeInTheDocument()
      expect(await menuOf(0)).toEqual([
        'Save to Watch later',
        'Save to playlist',
        'Share',
        'Remove from Liked videos',
      ])
    })

    /** A server whose list and count follow ratings; `fail`: the rating request fails. */
    /** `held`: the rating answers only when it resolves. */
    function mockRatings({ fail = false, held = Promise.resolve() } = {}) {
      let items = [likedItem(1), likedItem(2)]
      const sent: unknown[] = []
      mockApi({
        ...SIGNED_IN,
        'GET /api/me/liked': () => json(200, liked({ video_count: items.length })),
        'GET /api/me/liked/items': () => json(200, page(items)),
        'PUT /api/videos/video-00001/rating': async (request) => {
          sent.push(await request.json())
          await held
          if (fail) return json(500, { detail: 'Internal Server Error' })
          items = items.filter((each) => each.video.id !== 'video-00001')
          return json(200, { like_count: 0, my_rating: 'none' })
        },
      })
      return { sent }
    }

    it('takes the like back from the ⋮ menu, the row at once', async () => {
      let answer = () => {}
      const held = new Promise<void>((resolve) => (answer = resolve))
      const { sent } = mockRatings({ held })
      renderApp('/playlist?list=LL')

      await choose(0, 'Remove from Liked videos')

      // Gone before the server answers, as on YouTube; the count follows.
      expect(await rowTitles()).toEqual(['Video 2'])
      expect(screen.getByText('1 video')).toBeInTheDocument()
      expect(screen.queryByRole('status')).not.toBeInTheDocument()
      answer()
      expect(await screen.findByRole('status')).toHaveTextContent('Removed from Liked videos')
      expect(await rowTitles()).toEqual(['Video 2'])
      expect(sent).toEqual([{ rating: 'none' }])
    })

    it('brings the video back and says so when the like can’t be taken back', async () => {
      mockRatings({ fail: true })
      renderApp('/playlist?list=LL')

      await choose(0, 'Remove from Liked videos')

      expect(await screen.findByRole('status')).toHaveTextContent(
        'Couldn’t change the playlist. Try again.',
      )
      expect(await rowTitles()).toEqual(['Video 1', 'Video 2'])
    })

    it('shows an empty list without a date or Play all', async () => {
      mockLiked(liked({ video_count: 0, thumbnail_url: null, updated_at: null }), [])
      renderApp('/playlist?list=LL')

      expect(await screen.findByText('No videos in this playlist yet')).toBeInTheDocument()
      expect(screen.getByText('No videos')).toBeInTheDocument()
      expect(screen.queryByText(/^Updated/)).not.toBeInTheDocument()
      expect(screen.queryByRole('link', { name: /Play all/ })).not.toBeInTheDocument()
    })

    it('asks a guest to sign in', async () => {
      const fetch = mockApi(GUEST)
      renderApp('/playlist?list=LL')

      expect(
        await screen.findByRole('heading', { name: 'Enjoy your favorite videos' }),
      ).toBeInTheDocument()
      // YouTube's words on the You page for a guest.
      expect(
        screen.getByText('Sign in to access videos that you’ve liked or saved'),
      ).toBeInTheDocument()
      const urls = fetch.mock.calls.map(([request]) => new URL(request.url).pathname)
      expect(urls.filter((url) => url.startsWith('/api/me/liked'))).toEqual([])
    })
  })
})
