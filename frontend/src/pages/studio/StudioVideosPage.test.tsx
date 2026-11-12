import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { formatDate } from '../../lib/format'
import { ANNA, json, mockApi } from '../../test/api'
import { intersectAll } from '../../test/observers'
import { renderApp } from '../../test/render'
import { own, page } from '../../test/videos'
import type { VideoStatus } from '../../videos/types'

const SIGNED_IN = { 'GET /api/auth/me': () => json(200, ANNA) }

/** The query string of each list request, in order. */
const listRequests = (fetch: ReturnType<typeof mockApi>) =>
  fetch.mock.calls
    .map(([request]) => new URL(request.url))
    .filter((url) => url.pathname === '/api/me/videos')
    .map((url) => url.search)

const rowOf = (title: string) => {
  const row = screen.getByRole('link', { name: title }).closest('tr')
  if (!row) throw new Error(`No row for ${title}`)
  return within(row)
}

describe('StudioVideosPage', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('sends a guest to sign in and back here', async () => {
    mockApi({ 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) })
    const router = renderApp('/studio/videos')

    await screen.findByRole('heading', { name: 'Sign in' })
    expect(router.state.location.pathname).toBe('/login')
    expect(router.state.location.state).toEqual({ from: '/studio/videos' })
  })

  it('shows skeleton rows while the list loads', async () => {
    mockApi({ ...SIGNED_IN, 'GET /api/me/videos': () => new Promise<Response>(() => {}) })
    renderApp('/studio/videos')

    expect(await screen.findByRole('table', { name: 'Loading videos' })).toHaveAttribute(
      'aria-busy',
      'true',
    )
  })

  it('lists every video with its visibility, status, date and counts', async () => {
    const ready = own(1, {
      title: 'Sintel – trailer',
      description: 'A lone girl searches for a baby dragon.',
      visibility: 'public',
      view_count: 2_384_112,
      comment_count: 12,
      like_count: 1_204,
    })
    mockApi({
      ...SIGNED_IN,
      'GET /api/me/videos': () =>
        json(
          200,
          page([
            ready,
            own(2, {
              title: 'Still processing',
              status: 'processing',
              visibility: 'unlisted',
              thumbnail_url: null,
              duration_sec: null,
            }),
            own(3, {
              title: 'Never uploaded',
              status: 'uploading',
              visibility: 'private',
              thumbnail_url: null,
              duration_sec: null,
            }),
          ]),
        ),
    })
    renderApp('/studio/videos')

    expect(await screen.findByRole('link', { name: 'Sintel – trailer' })).toHaveAttribute(
      'href',
      '/watch?v=video-00001',
    )
    const first = rowOf('Sintel – trailer')
    expect(first.getByText('A lone girl searches for a baby dragon.')).toBeInTheDocument()
    expect(first.getByText('Public')).toBeInTheDocument()
    expect(first.getByText('None')).toBeInTheDocument()
    expect(first.getByText('Ready')).toBeInTheDocument()
    expect(first.getByText(formatDate(ready.created_at))).toBeInTheDocument()
    expect(first.getByText('Published')).toBeInTheDocument()
    expect(first.getByText('2,384,112')).toBeInTheDocument()
    expect(first.getByText('12')).toBeInTheDocument()
    expect(first.getByText('1,204')).toBeInTheDocument()

    const processing = rowOf('Still processing')
    expect(processing.getByText('Unlisted')).toBeInTheDocument()
    expect(processing.getByText('Processing')).toBeInTheDocument()
    expect(processing.getByText('Uploaded')).toBeInTheDocument()
    // A draft says so in Visibility, as in Studio, and only there.
    const draft = rowOf('Never uploaded')
    expect(draft.getByText('Draft')).toBeInTheDocument()
    expect(draft.queryByText('Private')).not.toBeInTheDocument()
    expect(document.title).toBe('Channel content - ViTube')
  })

  it('shows a video a moderator hid in Restrictions', async () => {
    mockApi({
      ...SIGNED_IN,
      'GET /api/me/videos': () =>
        json(200, page([own(1, { title: 'Fake giveaway', is_hidden: true })])),
    })
    renderApp('/studio/videos')

    await screen.findByRole('link', { name: 'Fake giveaway' })
    expect(rowOf('Fake giveaway').getByText('Hidden by a moderator')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Restrictions' })).toBeInTheDocument()
  })

  it('says why a video failed to process', async () => {
    mockApi({
      ...SIGNED_IN,
      'GET /api/me/videos': () =>
        json(
          200,
          page([
            own(1, {
              title: 'Broken file',
              status: 'failed',
              error_message: 'The file is not a video',
              thumbnail_url: null,
              duration_sec: null,
            }),
          ]),
        ),
    })
    renderApp('/studio/videos')

    await screen.findByRole('link', { name: 'Broken file' })
    expect(rowOf('Broken file').getByText('Processing failed')).toBeInTheDocument()
    expect(rowOf('Broken file').getByText('The file is not a video')).toBeInTheDocument()
  })

  it('loads the next page by its cursor when the end of the list comes into view', async () => {
    const fetch = mockApi({
      ...SIGNED_IN,
      'GET /api/me/videos': (request) =>
        new URL(request.url).searchParams.get('cursor') === 'next'
          ? json(200, page([own(2)]))
          : json(200, page([own(1)], 'next')),
    })
    renderApp('/studio/videos')
    await screen.findByRole('link', { name: 'Video 1' })

    act(() => intersectAll())
    expect(await screen.findByRole('link', { name: 'Video 2' })).toBeInTheDocument()
    expect(listRequests(fetch)).toEqual(['', '?cursor=next'])
  })

  it('shows the new status while a video processes, then stops asking', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let status: VideoStatus = 'processing'
    const fetch = mockApi({
      ...SIGNED_IN,
      'GET /api/me/videos': () => json(200, page([own(1, { status })])),
    })
    renderApp('/studio/videos')
    expect(await screen.findByText('Processing')).toBeInTheDocument()

    status = 'ready'
    await act(() => vi.advanceTimersByTimeAsync(2000))
    expect(await screen.findByText('Ready')).toBeInTheDocument()

    const asked = listRequests(fetch).length
    await act(() => vi.advanceTimersByTimeAsync(10_000))
    expect(listRequests(fetch)).toHaveLength(asked)
  })

  it('says so when the user has no videos, with a way to upload one', async () => {
    mockApi({
      ...SIGNED_IN,
      'GET /api/me/videos': () => json(200, page([])),
      'GET /api/videos/upload-limits': () =>
        json(200, { max_size_bytes: 1024 ** 3, max_duration_sec: 1800 }),
    })
    renderApp('/studio/videos')

    expect(await screen.findByText('No content available')).toBeInTheDocument()
    const buttons = screen.getAllByRole('button', { name: 'Upload videos' })
    expect(buttons).toHaveLength(2) // by the heading and in the empty list
    await userEvent.click(buttons[1])
    expect(screen.getByRole('dialog', { name: 'Upload videos' })).toBeInTheDocument()
  })

  it('opens the upload dialog from the heading', async () => {
    mockApi({
      ...SIGNED_IN,
      'GET /api/me/videos': () => json(200, page([own(1)])),
      'GET /api/videos/upload-limits': () =>
        json(200, { max_size_bytes: 1024 ** 3, max_duration_sec: 1800 }),
    })
    renderApp('/studio/videos')
    await screen.findByRole('link', { name: 'Video 1' })

    await userEvent.click(screen.getByRole('button', { name: 'Upload videos' }))

    expect(screen.getByRole('dialog', { name: 'Upload videos' })).toBeInTheDocument()
    expect(screen.getByText('Drag and drop a video file to upload')).toBeInTheDocument()
  })

  it('offers a retry when the list fails to load', async () => {
    let calls = 0
    mockApi({
      ...SIGNED_IN,
      'GET /api/me/videos': () =>
        ++calls === 1 ? json(500, { detail: 'Server error' }) : json(200, page([own(1)])),
    })
    renderApp('/studio/videos')

    expect(await screen.findByRole('alert')).toHaveTextContent('Can’t load your videos')
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('link', { name: 'Video 1' })).toBeInTheDocument()
  })

  describe('Edit details', () => {
    /** The list answers with the video as it is now: an edit shows once it is saved. */
    function mockEdit(patch: (request: Request) => Response) {
      let video = own(1, { visibility: 'private' })
      const fetch = mockApi({
        ...SIGNED_IN,
        'GET /api/me/videos': () => json(200, page([video])),
        [`PATCH /api/videos/${video.id}`]: async (request) => {
          const changes = (await request.clone().json()) as object
          const response = await patch(request)
          if (response.ok) video = { ...video, ...changes }
          return response
        },
      })
      return fetch
    }

    async function openEdit() {
      renderApp('/studio/videos')
      await screen.findByRole('link', { name: 'Video 1' })
      await userEvent.click(rowOf('Video 1').getByRole('button', { name: 'Options for Video 1' }))
      await userEvent.click(screen.getByRole('menuitem', { name: 'Edit details' }))
      return within(screen.getByRole('dialog', { name: 'Video details' }))
    }

    it('saves only what changed, says so and shows it in the row', async () => {
      const fetch = mockEdit(() => json(200, {}))
      const dialog = await openEdit()

      const save = dialog.getByRole('button', { name: 'Save' })
      expect(save).toBeDisabled() // nothing changed yet
      const title = dialog.getByRole('textbox', { name: 'Title (required)' })
      await userEvent.clear(title)
      await userEvent.type(title, 'Sintel')
      await userEvent.click(dialog.getByRole('radio', { name: /Public/ }))
      await userEvent.click(save)

      expect(await screen.findByRole('status')).toHaveTextContent('Changes saved')
      expect(screen.queryByRole('dialog', { name: 'Video details' })).not.toBeInTheDocument()
      const patch = fetch.mock.calls.find(([request]) => request.method === 'PATCH')![0]
      expect(await patch.json()).toEqual({ title: 'Sintel', visibility: 'public' })
      expect(await screen.findByRole('link', { name: 'Sintel' })).toBeInTheDocument()
      expect(rowOf('Sintel').getByText('Public')).toBeInTheDocument()
    })

    it('needs a title', async () => {
      mockEdit(() => json(200, {}))
      const dialog = await openEdit()

      await userEvent.clear(dialog.getByRole('textbox', { name: 'Title (required)' }))

      expect(dialog.getByRole('button', { name: 'Save' })).toBeDisabled()
    })

    it('stays open with the reason when saving fails', async () => {
      mockEdit(() => json(422, { detail: 'Title is too long' }))
      const dialog = await openEdit()

      await userEvent.type(dialog.getByRole('textbox', { name: 'Description' }), ' More.')
      await userEvent.click(dialog.getByRole('button', { name: 'Save' }))

      expect(await dialog.findByRole('alert')).toHaveTextContent('Title is too long')
      expect(screen.getByRole('dialog', { name: 'Video details' })).toBeInTheDocument()
    })

    it('closes without saving on Cancel', async () => {
      const fetch = mockEdit(() => json(200, {}))
      const dialog = await openEdit()

      await userEvent.type(dialog.getByRole('textbox', { name: 'Description' }), ' More.')
      await userEvent.click(dialog.getByRole('button', { name: 'Cancel' }))

      expect(screen.queryByRole('dialog', { name: 'Video details' })).not.toBeInTheDocument()
      expect(fetch.mock.calls.some(([request]) => request.method === 'PATCH')).toBe(false)
    })
  })

  describe('Share privately', () => {
    const VIDEO = own(1, { visibility: 'private' })
    const ACCESS = `/api/videos/${VIDEO.id}/access`
    const person = (handle: string) => ({
      handle,
      name: handle,
      avatar_url: null,
      shared_at: '2026-11-12T10:00:00Z',
    })

    /** The access list as the server keeps it; `refuse` answers a share instead. */
    function mockSharing(refuse?: () => Response) {
      let people = [person('ben')]
      return mockApi({
        ...SIGNED_IN,
        'GET /api/me/videos': () => json(200, page([VIDEO])),
        [`GET ${ACCESS}`]: () => json(200, people),
        [`POST ${ACCESS}`]: async (request) => {
          if (refuse) return refuse()
          const { handle } = (await request.clone().json()) as { handle: string }
          people = [...people, person(handle)]
          return new Response(null, { status: 204 })
        },
        [`DELETE ${ACCESS}/ben`]: () => {
          people = people.filter((p) => p.handle !== 'ben')
          return new Response(null, { status: 204 })
        },
      })
    }

    async function openShare() {
      renderApp('/studio/videos')
      await screen.findByRole('link', { name: 'Video 1' })
      await userEvent.click(rowOf('Video 1').getByRole('button', { name: 'Options for Video 1' }))
      await userEvent.click(screen.getByRole('menuitem', { name: 'Share privately' }))
      return within(screen.getByRole('dialog', { name: 'Share privately' }))
    }

    it('adds a person by handle and says so', async () => {
      const fetch = mockSharing()
      const dialog = await openShare()
      expect(await dialog.findByText('@ben')).toBeInTheDocument()

      await userEvent.type(dialog.getByRole('textbox', { name: 'Handle' }), '@anna{Enter}')

      expect(await dialog.findByText('@anna')).toBeInTheDocument()
      expect(screen.getByRole('status')).toHaveTextContent('Shared with @anna')
      expect(dialog.getByRole('textbox', { name: 'Handle' })).toHaveValue('')
      const post = fetch.mock.calls.find(([request]) => request.method === 'POST')![0]
      expect(await post.json()).toEqual({ handle: 'anna' })
    })

    it('removes a person and says so', async () => {
      mockSharing()
      const dialog = await openShare()

      await userEvent.click(await dialog.findByRole('button', { name: 'Remove @ben' }))

      expect(await dialog.findByText('Only you can watch this video.')).toBeInTheDocument()
      expect(screen.getByRole('status')).toHaveTextContent('Removed @ben')
    })

    it('shows why a share was refused under the field', async () => {
      mockSharing(() => json(404, { detail: 'No user with this handle' }))
      const dialog = await openShare()

      await userEvent.type(dialog.getByRole('textbox', { name: 'Handle' }), 'nobody{Enter}')

      expect(await dialog.findByText('No user with this handle')).toBeInTheDocument()
      expect(dialog.getByRole('textbox', { name: 'Handle' })).toHaveAttribute(
        'aria-invalid',
        'true',
      )
    })

    it('checks the handle before asking the server', async () => {
      const fetch = mockSharing()
      const dialog = await openShare()

      await userEvent.type(dialog.getByRole('textbox', { name: 'Handle' }), 'a b{Enter}')

      expect(dialog.getByText('Enter a handle such as @anna')).toBeInTheDocument()
      expect(fetch.mock.calls.some(([request]) => request.method === 'POST')).toBe(false)
    })

    it('is offered for private videos only', async () => {
      mockApi({
        ...SIGNED_IN,
        'GET /api/me/videos': () => json(200, page([own(1, { visibility: 'unlisted' })])),
      })
      renderApp('/studio/videos')
      await screen.findByRole('link', { name: 'Video 1' })

      await userEvent.click(rowOf('Video 1').getByRole('button', { name: 'Options for Video 1' }))

      expect(screen.getByRole('menuitem', { name: 'Edit details' })).toBeInTheDocument()
      expect(screen.queryByRole('menuitem', { name: 'Share privately' })).not.toBeInTheDocument()
    })
  })

  it('is where Your videos in the guide leads', async () => {
    mockApi({ ...SIGNED_IN, 'GET /api/me/videos': () => json(200, page([])) })
    renderApp('/studio/videos')

    const link = await screen.findByRole('link', { name: 'Your videos' })
    expect(link).toHaveAttribute('href', '/studio/videos')
    expect(link).toHaveAttribute('aria-current', 'page')
  })
})
