import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ANNA, json, mockApi } from '../test/api'
import { channel } from '../test/channels'
import { mine } from '../test/playlists'
import { renderApp } from '../test/render'
import { detail, page } from '../test/videos'

const VIDEO = detail(1)
const SIGNED_IN = { 'GET /api/auth/me': () => json(200, ANNA) }
const GUEST = { 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) }

/** A watch page and the playlist API around it. */
function mockSave(handlers: Record<string, (request: Request) => Response | Promise<Response>>) {
  const base = `/api/videos/${VIDEO.id}`
  return mockApi({
    [`GET ${base}`]: () => json(200, VIDEO),
    [`GET ${base}/related`]: () => json(200, page([])),
    [`GET ${base}/comments`]: () => json(200, page([])),
    [`POST ${base}/views/start`]: () => json(204),
    [`GET /api/channels/${VIDEO.channel.handle}`]: () => json(200, channel()),
    'GET /api/me/subscriptions': () => json(200, page([])),
    ...handlers,
  })
}

async function openSave() {
  renderApp(`/watch?v=${VIDEO.id}`)
  await screen.findByRole('heading', { level: 1, name: VIDEO.title })
  await userEvent.click(screen.getByRole('button', { name: 'Save' }))
  return screen.getByRole('dialog', { name: 'Save video to...' })
}

const requests = (fetch: ReturnType<typeof mockApi>, method: string) =>
  fetch.mock.calls
    .map(([request]) => request)
    .filter((request) => request.method === method)
    .map((request) => new URL(request.url).pathname)

describe('SaveDialog', () => {
  it('asks a guest to sign in', async () => {
    mockSave(GUEST)
    renderApp(`/watch?v=${VIDEO.id}`)
    await screen.findByRole('heading', { level: 1, name: VIDEO.title })

    await userEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(screen.getByText('Want to watch this again later?')).toBeInTheDocument()
  })

  it('ticks the playlists that hold the video and toggles them', async () => {
    // Remembers what the requests changed, as the server does: a refetch shows it.
    const holds = new Map([
      [mine(1, null).id, true],
      [mine(2, null).id, false],
    ])
    const toggle = (saved: boolean) => (request: Request) => {
      holds.set(new URL(request.url).pathname.split('/')[3], saved)
      return json(204)
    }
    const fetch = mockSave({
      ...SIGNED_IN,
      'GET /api/me/playlists': () =>
        json(
          200,
          page([
            mine(1, holds.get(mine(1, null).id)!, { visibility: 'public' }),
            mine(2, holds.get(mine(2, null).id)!),
          ]),
        ),
      [`PUT /api/playlists/${mine(2, null).id}/items/${VIDEO.id}`]: toggle(true),
      [`DELETE /api/playlists/${mine(1, null).id}/items/${VIDEO.id}`]: toggle(false),
    })
    const dialog = await openSave()

    const first = await within(dialog).findByRole('checkbox', { name: /Playlist 1/ })
    const second = within(dialog).getByRole('checkbox', { name: /Playlist 2/ })
    expect(first).toBeChecked()
    expect(second).not.toBeChecked()
    expect(within(dialog).getByRole('img', { name: 'Public' })).toBeInTheDocument()

    await userEvent.click(second)
    await userEvent.click(first)

    await waitFor(() => expect(requests(fetch, 'DELETE')).toHaveLength(1))
    expect(requests(fetch, 'PUT')).toEqual([`/api/playlists/${mine(2, null).id}/items/${VIDEO.id}`])
    await waitFor(() => expect(second).toBeChecked())
    expect(first).not.toBeChecked()
    const query = fetch.mock.calls
      .map(([request]) => new URL(request.url))
      .find((url) => url.pathname === '/api/me/playlists')
    expect(query?.searchParams.get('video')).toBe(VIDEO.id)
  })

  it('creates a playlist with the video in it', async () => {
    const created = mine(3, false, { title: 'Trailers', visibility: 'public' })
    let body: unknown
    const fetch = mockSave({
      ...SIGNED_IN,
      'GET /api/me/playlists': () => json(200, page([])),
      'POST /api/playlists': async (request) => {
        body = await request.json()
        return json(201, created)
      },
      [`PUT /api/playlists/${created.id}/items/${VIDEO.id}`]: () => json(204),
    })
    const dialog = await openSave()

    await userEvent.click(within(dialog).getByRole('button', { name: 'Create new playlist' }))
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Trailers')
    expect(within(dialog).getByText('8/150')).toBeInTheDocument()
    await userEvent.selectOptions(within(dialog).getByLabelText('Privacy'), 'public')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create' }))

    await waitFor(() => expect(requests(fetch, 'PUT')).toHaveLength(1))
    expect(body).toEqual({
      title: 'Trailers',
      description: '',
      visibility: 'public',
    })
    expect(within(dialog).getByRole('button', { name: 'Create new playlist' })).toBeInTheDocument()
  })

  it('keeps the form open with the reason when creating fails', async () => {
    mockSave({
      ...SIGNED_IN,
      'GET /api/me/playlists': () => json(200, page([])),
      'POST /api/playlists': () => json(429, { detail: 'Too many attempts. Try again later.' }),
    })
    const dialog = await openSave()

    await userEvent.click(within(dialog).getByRole('button', { name: 'Create new playlist' }))
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Trailers')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create' }))

    expect(
      await within(dialog).findByText('Too many attempts. Try again later.'),
    ).toBeInTheDocument()
    expect(within(dialog).getByLabelText('Name')).toHaveValue('Trailers')
  })
})
