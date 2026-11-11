import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ANNA, json, mockApi } from '../test/api'
import { renderApp } from '../test/render'
import type { OwnVideo } from './api'

const GIB = 1024 ** 3

function video(changes: Partial<OwnVideo> = {}): OwnVideo {
  return {
    id: 'abcdefghijk',
    title: 'holiday',
    description: '',
    visibility: 'private',
    category: 'people',
    status: 'uploading',
    error_message: null,
    duration_sec: null,
    thumbnail_url: null,
    media_url: null,
    view_count: 0,
    like_count: 0,
    comment_count: 0,
    created_at: '2026-11-07T12:00:00Z',
    channel: { handle: ANNA.handle, name: ANNA.handle, avatar_url: null },
    ...changes,
  }
}

const READY = video({
  status: 'ready',
  duration_sec: 5,
  media_url: '/media/videos/0193/720p.mp4',
  thumbnail_url: '/media/thumbs/0193.jpg',
})

/** Stands in for XMLHttpRequest: the test drives progress and the answer. */
class FakeXhr {
  static last: FakeXhr | undefined
  method = ''
  url = ''
  headers: Record<string, string> = {}
  body: unknown
  status = 0
  statusText = ''
  response: unknown = null
  responseType = ''
  upload: { onprogress: ((event: ProgressEvent) => void) | null } = { onprogress: null }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  onabort: (() => void) | null = null

  open(method: string, url: string) {
    this.method = method
    this.url = url
  }
  setRequestHeader(name: string, value: string) {
    this.headers[name] = value
  }
  send(body: unknown) {
    this.body = body
    FakeXhr.last = this
  }
  abort() {
    this.onabort?.()
  }
  progress(loaded: number, total: number) {
    this.upload.onprogress?.({ lengthComputable: true, loaded, total } as ProgressEvent)
  }
  respond(status: number, response: unknown) {
    this.status = status
    this.response = response
    this.onload?.()
  }
}

function file(name = 'holiday.mp4', type = 'video/mp4', size = 1024): File {
  const blob = new File(['x'], name, { type })
  Object.defineProperty(blob, 'size', { value: size })
  return blob
}

async function openDialog() {
  renderApp('/')
  await userEvent.click(await screen.findByRole('button', { name: 'Create' }))
  return screen.getByRole('dialog', { name: 'Upload videos' })
}

async function pick(dialog: HTMLElement, chosen: File) {
  // No accept filter: a dropped file skips it, so the dialog must check the type itself.
  const user = userEvent.setup({ applyAccept: false })
  await user.upload(within(dialog).getByTestId('file-input'), chosen)
}

/** Waits for the upload request, then gives it an answer. */
async function answerUpload(status: number, response: unknown) {
  await waitFor(() => expect(FakeXhr.last).toBeDefined())
  FakeXhr.last!.respond(status, response)
}

describe('UploadDialog', () => {
  let detail: OwnVideo
  let api: ReturnType<typeof mockApi>

  beforeEach(() => {
    FakeXhr.last = undefined
    vi.stubGlobal('XMLHttpRequest', FakeXhr)
    document.cookie = 'csrf_token=token-123'
    detail = READY
    api = mockApi({
      'GET /api/auth/me': () => json(200, ANNA),
      'GET /api/videos/upload-limits': () =>
        json(200, { max_size_bytes: GIB, max_duration_sec: 1800 }),
      'POST /api/videos': () => json(201, video()),
      'GET /api/videos/abcdefghijk': () => json(200, detail),
      'PATCH /api/videos/abcdefghijk': async (request) =>
        json(200, { ...video(), ...((await request.clone().json()) as object) }),
    })
  })
  afterEach(() => {
    document.cookie = 'csrf_token=; max-age=0'
  })

  it('is offered to signed-in users only', async () => {
    mockApi({ 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) })
    renderApp('/')

    expect(await screen.findAllByRole('link', { name: 'Sign in' })).not.toHaveLength(0)
    expect(screen.queryByRole('button', { name: 'Create' })).not.toBeInTheDocument()
  })

  it('shows the limits before a file is picked', async () => {
    const dialog = await openDialog()

    expect(await within(dialog).findByText('Up to 1 GB and 30 minutes')).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'Select file' })).toBeInTheDocument()
  })

  it('uploads the picked file and shows it once processed', async () => {
    const dialog = await openDialog()
    await within(dialog).findByText('Up to 1 GB and 30 minutes')
    const chosen = file()

    await pick(dialog, chosen)

    // A draft named after the file, then the file itself with the CSRF token.
    const draft = api.mock.calls.find(([request]) => request.method === 'POST')![0]
    expect(await draft.json()).toEqual({
      title: 'holiday',
      description: '',
      visibility: 'private',
      category: 'people',
    })
    await waitFor(() => expect(FakeXhr.last).toBeDefined())
    const xhr = FakeXhr.last!
    expect([xhr.method, xhr.url, xhr.body]).toEqual(['PUT', '/api/videos/abcdefghijk/file', chosen])
    expect(xhr.headers['X-CSRF-Token']).toBe('token-123')

    xhr.progress(45, 100)
    expect(await within(dialog).findByText('Uploading 45%')).toBeInTheDocument()

    xhr.respond(200, video({ status: 'uploaded' }))

    const preview = await within(dialog).findByLabelText('Video preview')
    expect(preview).toHaveAttribute('src', READY.media_url)
    expect(preview).toHaveAttribute('poster', READY.thumbnail_url)
    expect(within(dialog).getByText('Processing complete')).toBeInTheDocument()
    expect(within(dialog).getByRole('link', { name: /watch\?v=abcdefghijk$/ })).toBeInTheDocument()
  })

  it('copies the video link', async () => {
    const user = userEvent.setup() // provides a clipboard, as a secure page has
    renderApp('/')
    await user.click(await screen.findByRole('button', { name: 'Create' }))
    const dialog = screen.getByRole('dialog', { name: 'Upload videos' })
    await pick(dialog, file())
    await answerUpload(200, video({ status: 'uploaded' }))

    await user.click(await within(dialog).findByRole('button', { name: 'Copy video link' }))

    expect(await navigator.clipboard.readText()).toBe(
      `${window.location.origin}/watch?v=abcdefghijk`,
    )
    expect(within(dialog).getByText('Link copied')).toBeInTheDocument()
  })

  it('says processing is going on while the worker has the video', async () => {
    detail = video({ status: 'processing' })
    const dialog = await openDialog()
    await pick(dialog, file())

    await answerUpload(200, video({ status: 'uploaded' }))

    expect(await within(dialog).findByText('Processing video…')).toBeInTheDocument()
    expect(within(dialog).getByText('Upload complete. Processing…')).toBeInTheDocument()
  })

  it('refuses a file over the size limit before sending it', async () => {
    const dialog = await openDialog()
    await within(dialog).findByText('Up to 1 GB and 30 minutes')

    await pick(dialog, file('big.mp4', 'video/mp4', GIB + 1))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'This file is larger than 1 GB.',
    )
    expect(api.mock.calls.some(([request]) => request.method === 'POST')).toBe(false)
  })

  it('refuses a file that is not a video', async () => {
    const dialog = await openDialog()

    await pick(dialog, file('notes.txt', 'text/plain'))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent('This file is not a video.')
  })

  it('explains a refused upload and sends the file again on Try again', async () => {
    const dialog = await openDialog()
    await within(dialog).findByText('Up to 1 GB and 30 minutes')
    await pick(dialog, file())

    await answerUpload(413, null) // nginx's own 413 page: no JSON

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'This file is larger than 1 GB.',
    )
    const first = FakeXhr.last
    await userEvent.click(within(dialog).getByRole('button', { name: 'Try again' }))
    expect(FakeXhr.last).not.toBe(first)
    expect(FakeXhr.last!.url).toBe('/api/videos/abcdefghijk/file')
  })

  it('asks to wait when too many uploads are going on', async () => {
    const dialog = await openDialog()
    await pick(dialog, file())

    await answerUpload(429, null) // nginx's per-IP limit: HTML, no JSON

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'Too many uploads at once. Wait for one to finish.',
    )
  })

  it('says why processing failed', async () => {
    detail = video({ status: 'failed', error_message: 'The file is not a video' })
    const dialog = await openDialog()
    await pick(dialog, file())

    await answerUpload(200, video({ status: 'uploaded' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'Processing failed. The file is not a video',
    )
  })

  it('saves the details', async () => {
    const dialog = await openDialog()
    await pick(dialog, file())
    await answerUpload(200, video({ status: 'uploaded' }))

    const title = within(dialog).getByLabelText('Title (required)')
    await userEvent.clear(title)
    await userEvent.type(title, 'Summer in Riga')
    await userEvent.type(within(dialog).getByLabelText('Description'), 'Sea and sun')
    const category = within(dialog).getByRole('combobox', { name: 'Category' })
    expect(category).toHaveDisplayValue('People & Blogs')
    await userEvent.selectOptions(
      category,
      within(category).getByRole('option', { name: 'Travel & Events' }),
    )
    await userEvent.click(within(dialog).getByRole('radio', { name: /Public/ }))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))

    expect(await within(dialog).findByText('Details saved')).toBeInTheDocument()
    const patch = api.mock.calls.find(([request]) => request.method === 'PATCH')![0]
    expect(await patch.json()).toEqual({
      title: 'Summer in Riga',
      description: 'Sea and sun',
      visibility: 'public',
      category: 'travel',
    })
  })

  it('asks before closing during an upload, and stops it when closed', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    const dialog = await openDialog()
    await pick(dialog, file())
    await waitFor(() => expect(FakeXhr.last).toBeDefined())
    const abort = vi.spyOn(FakeXhr.last!, 'abort')

    await userEvent.click(within(dialog).getByRole('button', { name: 'Close' }))
    expect(screen.getByRole('dialog', { name: /holiday/ })).toBeInTheDocument()

    await userEvent.click(within(dialog).getByRole('button', { name: 'Close' }))
    expect(confirm).toHaveBeenCalledTimes(2)
    expect(abort).toHaveBeenCalled()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
