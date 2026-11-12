import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import type { HistoryItem } from '../../history/api'

import { ANNA, json, mockApi } from '../../test/api'
import { renderApp } from '../../test/render'
import { page, summary } from '../../test/videos'

const GUEST = { 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) }
const SIGNED_IN = {
  'GET /api/auth/me': () => json(200, ANNA),
  'GET /api/me/subscriptions': () => json(200, page([])),
  'GET /api/me/history/progress': () => json(200, { 'video-00001': 11 }),
}

function daysAgo(days: number): string {
  const day = new Date()
  day.setDate(day.getDate() - days)
  return day.toISOString()
}

function entry(n: number, days = 0): HistoryItem {
  return {
    video: { ...summary(n), description: `About video ${n}` },
    watched_at: daysAgo(days),
  }
}

/** A history the server keeps: removals and clearing show on the next read. */
function mockHistory(items: HistoryItem[], fail = false) {
  let current = items
  return mockApi({
    ...SIGNED_IN,
    'GET /api/me/history': () => json(200, page(current)),
    'DELETE /api/me/history': () => {
      if (fail) return json(500, { detail: 'Internal error' })
      current = []
      return json(204)
    },
    ...Object.fromEntries(
      items.map(({ video }) => [
        `DELETE /api/me/history/${video.id}`,
        () => {
          if (fail) return json(500, { detail: 'Internal error' })
          current = current.filter((item) => item.video.id !== video.id)
          return json(204)
        },
      ]),
    ),
  })
}

async function openHistory() {
  renderApp('/feed/history')
  await screen.findByRole('heading', { level: 1, name: 'Watch history' })
}

const row = (title: string) => screen.getByRole('link', { name: title }).closest('article')!

describe('HistoryPage', () => {
  it('asks a guest to sign in', async () => {
    mockApi(GUEST)
    renderApp('/feed/history')
    const main = await screen.findByRole('main')
    expect(
      await within(main).findByRole('heading', { name: 'Keep track of what you watch' }),
    ).toBeInTheDocument()
    expect(within(main).getByRole('link', { name: 'Sign in' })).toBeInTheDocument()
    expect(document.title).toBe('Watch history - ViTube')
  })

  it('lists the watched videos by day, last first, with where the viewer stopped', async () => {
    mockHistory([entry(3), entry(2, 1), entry(1, 1)])
    await openHistory()

    const today = await screen.findByRole('region', { name: 'Today' })
    expect(
      within(today)
        .getAllByRole('heading', { level: 3 })
        .map((h) => h.textContent),
    ).toEqual(['Video 3'])
    const yesterday = screen.getByRole('region', { name: 'Yesterday' })
    expect(
      within(yesterday)
        .getAllByRole('heading', { level: 3 })
        .map((h) => h.textContent),
    ).toEqual(['Video 2', 'Video 1'])

    const first = row('Video 1')
    expect(within(first).getByText(/• 1K views/)).toBeInTheDocument()
    expect(within(first).getByRole('link', { name: 'Open Movie Club' })).toHaveAttribute(
      'href',
      '/@openmovieclub',
    )
    expect(within(first).getByText('About video 1')).toBeInTheDocument()
    // 11 of 33 s.
    const bar = await within(first).findByRole('progressbar', { hidden: true })
    expect(bar).toHaveAttribute('aria-valuenow', '33')
  })

  it('says when there is nothing yet', async () => {
    mockHistory([])
    await openHistory()
    expect(await screen.findByText('Videos you watch appear here.')).toBeInTheDocument()
  })

  it('removes a video with a toast', async () => {
    const fetch = mockHistory([entry(2), entry(1)])
    await openHistory()
    await screen.findByRole('link', { name: 'Video 1' })

    await userEvent.click(
      within(row('Video 1')).getByRole('button', { name: 'Remove from watch history' }),
    )

    expect(await screen.findByRole('status')).toHaveTextContent('Removed from watch history')
    expect(screen.queryByRole('link', { name: 'Video 1' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Video 2' })).toBeInTheDocument()
    const deletes = fetch.mock.calls
      .map(([request]) => request)
      .filter((request) => request.method === 'DELETE')
      .map((request) => new URL(request.url).pathname)
    expect(deletes).toEqual(['/api/me/history/video-00001'])
  })

  it('keeps the row and says so when removing fails', async () => {
    mockHistory([entry(1)], true)
    await openHistory()
    await screen.findByRole('link', { name: 'Video 1' })

    await userEvent.click(screen.getByRole('button', { name: 'Remove from watch history' }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Couldn’t remove the video. Try again.',
    )
    expect(screen.getByRole('link', { name: 'Video 1' })).toBeInTheDocument()
  })

  it('clears the whole history after a confirmation', async () => {
    mockHistory([entry(2), entry(1)])
    await openHistory()
    await screen.findByRole('link', { name: 'Video 1' })

    await userEvent.click(screen.getByRole('button', { name: 'Clear all watch history' }))
    const dialog = screen.getByRole('dialog', { name: 'Clear watch history?' })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Clear watch history' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Watch history cleared')
    await waitFor(() => expect(screen.queryByRole('link', { name: 'Video 1' })).toBeNull())
    expect(screen.getByText('Videos you watch appear here.')).toBeInTheDocument()
  })

  it('clears nothing when the viewer cancels', async () => {
    const fetch = mockHistory([entry(1)])
    await openHistory()
    await screen.findByRole('link', { name: 'Video 1' })

    await userEvent.click(screen.getByRole('button', { name: 'Clear all watch history' }))
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.getByRole('link', { name: 'Video 1' })).toBeInTheDocument()
    expect(fetch.mock.calls.some(([request]) => request.method === 'DELETE')).toBe(false)
  })
})
