import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import type {
  HiddenPage,
  ModeratedComment,
  ModeratedVideo,
  ReportCase,
  ReportPage,
} from '../../moderation/api'
import { ANNA, json, mockApi } from '../../test/api'
import { renderApp } from '../../test/render'

const MODERATOR = { ...ANNA, role: 'moderator' } as const
const ADMIN = { ...ANNA, role: 'admin' } as const

function moderated(id: string, changes: Partial<ModeratedVideo> = {}): ModeratedVideo {
  return {
    id,
    title: `Video ${id}`,
    thumbnail_url: `/media/thumbs/${id}.jpg`,
    duration_sec: 61,
    status: 'ready',
    visibility: 'public',
    is_hidden: false,
    created_at: '2026-11-10T12:00:00Z',
    channel: { handle: 'user-owner123', name: 'user-owner123', avatar_url: null },
    ...changes,
  }
}

function reportCase(id: string, changes: Partial<ReportCase> = {}): ReportCase {
  return {
    video: moderated(id),
    comment: null,
    report_count: 2,
    reasons: ['harassment', 'spam'],
    notes: ['Mocks a classmate'],
    last_reported_at: '2026-11-11T12:00:00Z',
    ...changes,
  }
}

function commentCase(id: string, changes: Partial<ModeratedComment> = {}): ReportCase {
  return {
    ...reportCase('vvvvvvvvvvv'),
    video: null,
    comment: {
      id,
      text: 'Buy followers at example.com',
      author: { handle: 'user-spammer1', name: 'user-spammer1', avatar_url: null },
      published_at: '2026-11-11T10:00:00Z',
      is_reply: false,
      is_deleted: false,
      video: moderated('vvvvvvvvvvv'),
      ...changes,
    },
    reasons: ['spam'],
    notes: [],
  }
}

const page = (items: ReportCase[]): ReportPage => ({ items, next_cursor: null })
const hiddenPage = (items: ModeratedVideo[]): HiddenPage => ({ items, next_cursor: null })
const noContent = () => new Response(null, { status: 204 })

describe('moderation page', () => {
  it('asks a guest to sign in', async () => {
    mockApi({ 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) })
    renderApp('/moderation')

    expect(await screen.findByText('Sign in to review reports')).toBeInTheDocument()
    expect(within(screen.getByRole('main')).getByRole('link', { name: 'Sign in' })).toHaveAttribute(
      'href',
      '/login',
    )
  })

  it("is not there for a user who can't moderate", async () => {
    mockApi({ 'GET /api/auth/me': () => json(200, ANNA) })
    renderApp('/moderation')

    expect(await screen.findByText("This page isn't available")).toBeInTheDocument()
  })

  it('lists reported videos with their reasons and notes', async () => {
    mockApi({
      'GET /api/auth/me': () => json(200, MODERATOR),
      'GET /api/moderation/reports': () =>
        json(
          200,
          page([reportCase('aaaaaaaaaaa'), reportCase('bbbbbbbbbbb', { report_count: 1 })]),
        ),
    })
    renderApp('/moderation')

    const list = await screen.findByRole('list', { name: 'Reports' })
    const [first, second] = Array.from(list.children) as HTMLElement[]
    expect(within(first).getByRole('link', { name: 'Video aaaaaaaaaaa' })).toHaveAttribute(
      'href',
      '/watch?v=aaaaaaaaaaa',
    )
    expect(within(first).getByText('2 reports')).toBeInTheDocument()
    expect(within(first).getByText('Harassment or bullying')).toBeInTheDocument()
    expect(within(first).getByText('Spam or misleading')).toBeInTheDocument()
    expect(within(first).getByText('Mocks a classmate')).toBeInTheDocument()
    expect(within(second).getByText('1 report')).toBeInTheDocument()
  })

  it('says when there is nothing to review', async () => {
    mockApi({
      'GET /api/auth/me': () => json(200, MODERATOR),
      'GET /api/moderation/reports': () => json(200, page([])),
    })
    renderApp('/moderation')

    expect(await screen.findByText('No open reports')).toBeInTheDocument()
  })

  it('hides a video for the chosen reason and drops it from the queue', async () => {
    let queue = [reportCase('aaaaaaaaaaa')]
    const fetch = mockApi({
      'GET /api/auth/me': () => json(200, MODERATOR),
      'GET /api/moderation/reports': () => json(200, page(queue)),
      'POST /api/moderation/videos/aaaaaaaaaaa/hide': () => {
        queue = []
        return new Response(null, { status: 204 })
      },
    })
    renderApp('/moderation')

    await userEvent.click(await screen.findByRole('button', { name: 'Hide “Video aaaaaaaaaaa”' }))
    const dialog = within(screen.getByRole('dialog', { name: 'Hide video' }))
    // Starts from a reason the viewers gave.
    expect(dialog.getByRole('radio', { name: 'Harassment or bullying' })).toBeChecked()
    await userEvent.click(dialog.getByRole('radio', { name: 'Violent or repulsive content' }))
    await userEvent.click(dialog.getByRole('button', { name: 'Hide' }))

    expect(await screen.findByText('No open reports')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Video hidden')
    const hideCall = fetch.mock.calls.find(([request]) => request.method === 'POST')
    expect(await hideCall?.[0].json()).toEqual({ reason: 'violent' })
  })

  it('keeps the dialog open with the reason when hiding fails', async () => {
    mockApi({
      'GET /api/auth/me': () => json(200, MODERATOR),
      'GET /api/moderation/reports': () => json(200, page([reportCase('aaaaaaaaaaa')])),
      'POST /api/moderation/videos/aaaaaaaaaaa/hide': () =>
        json(404, { detail: 'Video not found' }),
    })
    renderApp('/moderation')

    await userEvent.click(await screen.findByRole('button', { name: 'Hide “Video aaaaaaaaaaa”' }))
    const dialog = within(screen.getByRole('dialog', { name: 'Hide video' }))
    await userEvent.click(dialog.getByRole('button', { name: 'Hide' }))

    await waitFor(() => expect(dialog.getByRole('alert')).toHaveTextContent('Video not found'))
  })

  it('dismisses the reports of a video', async () => {
    let queue = [reportCase('aaaaaaaaaaa')]
    const fetch = mockApi({
      'GET /api/auth/me': () => json(200, MODERATOR),
      'GET /api/moderation/reports': () => json(200, page(queue)),
      'POST /api/moderation/videos/aaaaaaaaaaa/dismiss': () => {
        queue = []
        return noContent()
      },
    })
    renderApp('/moderation')

    await userEvent.click(
      await screen.findByRole('button', { name: 'Dismiss reports of “Video aaaaaaaaaaa”' }),
    )

    expect(await screen.findByText('No open reports')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Reports dismissed')
    expect(fetch.mock.calls.some(([request]) => request.url.endsWith('/dismiss'))).toBe(true)
  })

  it("offers no actions on the moderator's own video", async () => {
    const own = moderated('aaaaaaaaaaa', {
      channel: { handle: MODERATOR.handle, name: MODERATOR.handle, avatar_url: null },
    })
    mockApi({
      'GET /api/auth/me': () => json(200, MODERATOR),
      'GET /api/moderation/reports': () =>
        json(200, page([reportCase('aaaaaaaaaaa', { video: own })])),
    })
    renderApp('/moderation')

    expect(await screen.findByText('Your video: another moderator decides')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Hide|Dismiss/ })).not.toBeInTheDocument()
  })

  it('lists hidden videos in their tab and restores one', async () => {
    let hidden = [moderated('ccccccccccc', { is_hidden: true })]
    mockApi({
      'GET /api/auth/me': () => json(200, MODERATOR),
      'GET /api/moderation/reports': () => json(200, page([])),
      'GET /api/moderation/videos/hidden': () => json(200, hiddenPage(hidden)),
      'POST /api/moderation/videos/ccccccccccc/restore': () => {
        hidden = []
        return noContent()
      },
    })
    const router = renderApp('/moderation')

    await userEvent.click(await screen.findByRole('link', { name: 'Hidden videos' }))
    expect(router.state.location.pathname).toBe('/moderation/hidden')
    expect(screen.getByRole('link', { name: 'Hidden videos' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    const list = await screen.findByRole('list', { name: 'Hidden videos' })
    expect(within(list).getByText('Hidden')).toBeInTheDocument()
    await userEvent.click(within(list).getByRole('button', { name: 'Restore “Video ccccccccccc”' }))

    expect(await screen.findByText('No hidden videos')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Video restored')
  })

  it('says why a restore failed', async () => {
    mockApi({
      'GET /api/auth/me': () => json(200, MODERATOR),
      'GET /api/moderation/videos/hidden': () =>
        json(200, hiddenPage([moderated('ccccccccccc', { is_hidden: true })])),
      'POST /api/moderation/videos/ccccccccccc/restore': () =>
        json(403, { detail: 'Another moderator decides about your own video' }),
    })
    renderApp('/moderation/hidden')

    await userEvent.click(
      await screen.findByRole('button', { name: 'Restore “Video ccccccccccc”' }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Another moderator decides about your own video',
    )
  })

  it('shows a reported comment with its video and deletes it after asking', async () => {
    let queue = [commentCase('0193a5c2-0000-7000-8000-000000000001')]
    const fetch = mockApi({
      'GET /api/auth/me': () => json(200, MODERATOR),
      'GET /api/moderation/reports': () => json(200, page(queue)),
      'DELETE /api/moderation/comments/0193a5c2-0000-7000-8000-000000000001': () => {
        queue = []
        return noContent()
      },
    })
    renderApp('/moderation')

    expect(await screen.findByText('Buy followers at example.com')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '@user-spammer1' })).toHaveAttribute(
      'href',
      '/@user-spammer1',
    )
    expect(screen.getByText(/Comment on/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Delete comment by @user-spammer1' }))
    const dialog = within(screen.getByRole('dialog', { name: 'Delete comment' }))
    expect(dialog.getByText(/with its replies/)).toBeInTheDocument()
    await userEvent.click(dialog.getByRole('button', { name: 'Delete' }))

    expect(await screen.findByText('No open reports')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Comment deleted')
    expect(fetch.mock.calls.some(([request]) => request.method === 'DELETE')).toBe(true)
  })

  it('dismisses the reports of a comment', async () => {
    let queue = [commentCase('0193a5c2-0000-7000-8000-000000000001', { is_reply: true })]
    mockApi({
      'GET /api/auth/me': () => json(200, MODERATOR),
      'GET /api/moderation/reports': () => json(200, page(queue)),
      'POST /api/moderation/comments/0193a5c2-0000-7000-8000-000000000001/dismiss': () => {
        queue = []
        return noContent()
      },
    })
    renderApp('/moderation')

    expect(await screen.findByText(/Reply on/)).toBeInTheDocument()
    await userEvent.click(
      screen.getByRole('button', { name: 'Dismiss reports of comment by @user-spammer1' }),
    )

    expect(await screen.findByText('No open reports')).toBeInTheDocument()
  })

  it("offers no actions on the moderator's own comment", async () => {
    const author = { handle: MODERATOR.handle, name: MODERATOR.handle, avatar_url: null }
    mockApi({
      'GET /api/auth/me': () => json(200, MODERATOR),
      'GET /api/moderation/reports': () =>
        json(200, page([commentCase('0193a5c2-0000-7000-8000-000000000001', { author })])),
    })
    renderApp('/moderation')

    expect(await screen.findByText('Your comment: another moderator decides')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Delete|Dismiss/ })).not.toBeInTheDocument()
  })

  it('shows the accounts tab to admins only', async () => {
    mockApi({
      'GET /api/auth/me': () => json(200, MODERATOR),
      'GET /api/moderation/reports': () => json(200, page([])),
    })
    renderApp('/moderation')

    expect(await screen.findByRole('link', { name: 'Hidden videos' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Accounts' })).not.toBeInTheDocument()
  })

  it('lets an admin terminate the channel behind a reported video', async () => {
    const fetch = mockApi({
      'GET /api/auth/me': () => json(200, ADMIN),
      'GET /api/moderation/reports': () => json(200, page([reportCase('aaaaaaaaaaa')])),
      'PUT /api/moderation/users/user-owner123/status': () => noContent(),
    })
    renderApp('/moderation')

    await userEvent.click(
      await screen.findByRole('button', { name: 'More actions for @user-owner123' }),
    )
    await userEvent.click(screen.getByRole('menuitem', { name: 'Restrict @user-owner123' }))
    const dialog = within(screen.getByRole('dialog', { name: 'Restrict account' }))
    expect(dialog.getByRole('radio', { name: /^Ban/ })).toBeChecked()
    await userEvent.click(dialog.getByRole('radio', { name: /^Terminate channel/ }))
    await userEvent.type(
      dialog.getByRole('textbox', { name: 'Reason for the audit log' }),
      'Scam channel',
    )
    await userEvent.click(dialog.getByRole('button', { name: 'Terminate' }))

    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'Restrict account' })).not.toBeInTheDocument(),
    )
    expect(screen.getByRole('status')).toHaveTextContent('@user-owner123’s channel terminated')
    const call = fetch.mock.calls.find(([request]) => request.method === 'PUT')
    expect(await call?.[0].json()).toEqual({ status: 'terminated', reason: 'Scam channel' })
  })

  it('offers moderators no account menu', async () => {
    mockApi({
      'GET /api/auth/me': () => json(200, MODERATOR),
      'GET /api/moderation/reports': () => json(200, page([reportCase('aaaaaaaaaaa')])),
    })
    renderApp('/moderation')

    expect(await screen.findByRole('button', { name: /^Hide/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /More actions/ })).not.toBeInTheDocument()
  })

  it('lists restricted accounts and reinstates one', async () => {
    let accounts = [
      {
        channel: { handle: 'user-spammer1', name: 'user-spammer1', avatar_url: null },
        status: 'terminated' as const,
      },
    ]
    const fetch = mockApi({
      'GET /api/auth/me': () => json(200, ADMIN),
      'GET /api/moderation/users': () => json(200, { items: accounts, next_cursor: null }),
      'PUT /api/moderation/users/user-spammer1/status': () => {
        accounts = []
        return noContent()
      },
    })
    renderApp('/moderation/accounts')

    const list = within(await screen.findByRole('list', { name: 'Restricted accounts' }))
    expect(list.getByText('Channel terminated')).toBeInTheDocument()
    await userEvent.click(list.getByRole('button', { name: 'Reinstate @user-spammer1' }))

    expect(await screen.findByText('No restricted accounts')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('@user-spammer1 reinstated')
    const call = fetch.mock.calls.find(([request]) => request.method === 'PUT')
    expect(await call?.[0].json()).toEqual({ status: 'active', reason: '' })
  })

  it('filters accounts by status', async () => {
    const fetch = mockApi({
      'GET /api/auth/me': () => json(200, ADMIN),
      'GET /api/moderation/users': () => json(200, { items: [], next_cursor: null }),
    })
    renderApp('/moderation/accounts')

    await userEvent.click(await screen.findByRole('button', { name: 'Banned' }))

    await waitFor(() =>
      expect(
        fetch.mock.calls.some(([request]) => new URL(request.url).search === '?status=banned'),
      ).toBe(true),
    )
  })

  it('keeps the accounts tab from moderators', async () => {
    mockApi({ 'GET /api/auth/me': () => json(200, MODERATOR) })
    renderApp('/moderation/accounts')

    expect(await screen.findByText("This page isn't available")).toBeInTheDocument()
  })

  it('shows admins who did what in the audit log', async () => {
    const at = '2026-11-11T12:00:00Z'
    const entry = {
      created_at: at,
      source: 'api' as const,
      actor: { handle: 'user-mod00001', name: 'user-mod00001', avatar_url: null },
      by: null,
    }
    mockApi({
      'GET /api/auth/me': () => json(200, ADMIN),
      'GET /api/moderation/audit-log': () =>
        json(200, {
          items: [
            {
              ...entry,
              id: '0193a5c2-0000-7000-8000-000000000003',
              source: 'cli',
              actor: null,
              by: 'admin@example.com',
              action: 'set_user_status',
              target: {
                type: 'user',
                label: '@user-spammer1',
                video_id: null,
                handle: 'user-spammer1',
              },
              details: { from: 'active', to: 'terminated', reason: 'Scam channel' },
            },
            {
              ...entry,
              id: '0193a5c2-0000-7000-8000-000000000002',
              action: 'hide_video',
              target: {
                type: 'video',
                label: 'Fake giveaway',
                video_id: 'aaaaaaaaaaa',
                handle: null,
              },
              details: { reason: 'spam', reports: 2 },
            },
            {
              ...entry,
              id: '0193a5c2-0000-7000-8000-000000000001',
              action: 'restore_video',
              target: { type: 'video', label: '', video_id: null, handle: null },
              details: {},
            },
          ],
          next_cursor: null,
        }),
    })
    renderApp('/moderation/audit')

    const list = await screen.findByRole('list', { name: 'Audit log' })
    const [cli, hid, gone] = Array.from(list.children) as HTMLElement[]
    expect(cli).toHaveTextContent('Command line terminated the channel @user-spammer1')
    expect(cli).toHaveTextContent('“Scam channel”. Run by admin@example.com')
    expect(hid).toHaveTextContent('@user-mod00001 hid “Fake giveaway”')
    expect(hid).toHaveTextContent('Spam or misleading. 2 reports closed')
    expect(within(hid).getByRole('link', { name: '“Fake giveaway”' })).toHaveAttribute(
      'href',
      '/watch?v=aaaaaaaaaaa',
    )
    expect(gone).toHaveTextContent('restored (deleted)')
    expect(screen.getByRole('link', { name: 'Audit log' })).toHaveAttribute('aria-current', 'page')
  })

  it('says when an account behind an entry was deleted', async () => {
    mockApi({
      'GET /api/auth/me': () => json(200, ADMIN),
      'GET /api/moderation/audit-log': () =>
        json(200, {
          items: [
            {
              id: '0193a5c2-0000-7000-8000-000000000001',
              created_at: '2026-11-11T12:00:00Z',
              source: 'api',
              actor: null,
              by: null,
              action: 'restore_video',
              target: { type: 'video', label: '', video_id: null, handle: null },
              details: {},
            },
          ],
          next_cursor: null,
        }),
    })
    renderApp('/moderation/audit')

    const list = await screen.findByRole('list', { name: 'Audit log' })
    expect(list).toHaveTextContent('A deleted account restored (deleted)')
  })

  describe('audit log filters', () => {
    const empty = () => json(200, { items: [], next_cursor: null })
    const queries = (fetch: ReturnType<typeof mockApi>) =>
      fetch.mock.calls
        .map(([request]) => new URL(request.url))
        .filter((url) => url.pathname === '/api/moderation/audit-log')
        .map((url) => url.search)

    it('narrows the log to the actions of a chip', async () => {
      const fetch = mockApi({
        'GET /api/auth/me': () => json(200, ADMIN),
        'GET /api/moderation/audit-log': empty,
      })
      renderApp('/moderation/audit')

      await userEvent.click(await screen.findByRole('button', { name: 'Dismissed' }))

      await waitFor(() =>
        expect(queries(fetch)).toContain('?action=dismiss_video&action=dismiss_comment'),
      )
      expect(screen.getByRole('button', { name: 'Dismissed' })).toHaveAttribute(
        'aria-pressed',
        'true',
      )
    })

    it('finds what an account did and what was done to it, by handle', async () => {
      const fetch = mockApi({
        'GET /api/auth/me': () => json(200, ADMIN),
        'GET /api/moderation/audit-log': empty,
      })
      renderApp('/moderation/audit')

      await userEvent.type(await screen.findByLabelText('Done by'), '@user-mod00001{Enter}')
      await waitFor(() => expect(queries(fetch)).toContain('?actor=user-mod00001'))

      await userEvent.type(screen.getByLabelText('About account'), 'user-spammer1{Enter}')
      await waitFor(() =>
        expect(queries(fetch)).toContain('?actor=user-mod00001&account=user-spammer1'),
      )
    })

    it('refuses what is not a handle without asking the server', async () => {
      const fetch = mockApi({
        'GET /api/auth/me': () => json(200, ADMIN),
        'GET /api/moderation/audit-log': empty,
      })
      renderApp('/moderation/audit')
      const field = await screen.findByLabelText('Done by')
      await waitFor(() => expect(queries(fetch)).toEqual(['']))

      await userEvent.type(field, 'no spaces{Enter}')

      expect(field).toHaveAccessibleDescription('Enter a handle, like @name')
      expect(queries(fetch)).toEqual([''])
    })

    it('shows what was run from the command line', async () => {
      const fetch = mockApi({
        'GET /api/auth/me': () => json(200, ADMIN),
        'GET /api/moderation/audit-log': empty,
      })
      renderApp('/moderation/audit?by=user-mod00001')

      await userEvent.click(await screen.findByRole('button', { name: 'Command line' }))

      await waitFor(() => expect(queries(fetch)).toContain('?source=cli'))
      expect(screen.getByLabelText('Done by')).toBeDisabled()
      expect(screen.getByLabelText('Done by')).toHaveValue('')
    })

    it('takes an empty handle in the address for no filter', async () => {
      const fetch = mockApi({
        'GET /api/auth/me': () => json(200, ADMIN),
        'GET /api/moderation/audit-log': empty,
      })
      renderApp('/moderation/audit?by=&about=')

      expect(await screen.findByText('Nothing logged yet')).toBeInTheDocument()
      expect(queries(fetch)).toEqual([''])
    })

    it('reads the filters from the address and clears them', async () => {
      const fetch = mockApi({
        'GET /api/auth/me': () => json(200, ADMIN),
        'GET /api/moderation/audit-log': empty,
      })
      renderApp('/moderation/audit?action=hidden&about=user-spammer1')

      expect(await screen.findByText('No entries match these filters')).toBeInTheDocument()
      expect(queries(fetch)).toEqual(['?action=hide_video&account=user-spammer1'])
      expect(screen.getByLabelText('About account')).toHaveValue('user-spammer1')

      await userEvent.click(
        within(screen.getByRole('main')).getAllByRole('button', { name: 'Clear filters' })[0],
      )

      expect(await screen.findByText('Nothing logged yet')).toBeInTheDocument()
      expect(screen.getByLabelText('About account')).toHaveValue('')
      expect(screen.getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'true')
    })
  })

  it('keeps the audit log from moderators', async () => {
    mockApi({ 'GET /api/auth/me': () => json(200, MODERATOR) })
    renderApp('/moderation/audit')

    expect(await screen.findByText("This page isn't available")).toBeInTheDocument()
  })
})
