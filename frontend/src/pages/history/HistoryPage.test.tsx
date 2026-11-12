import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { HistoryItem } from '../../history/api'

import { ANNA, json, mockApi } from '../../test/api'
import { renderApp } from '../../test/render'
import { page, summary } from '../../test/videos'

const GUEST = { 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) }
const SIGNED_IN = {
  'GET /api/auth/me': () => json(200, ANNA),
  'GET /api/me/subscriptions': () => json(200, page([])),
}

function entry(n: number): HistoryItem {
  return { video: summary(n), watched_at: '2026-11-12T10:00:00Z' }
}

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

  it('lists the watched videos, last first', async () => {
    mockApi({ ...SIGNED_IN, 'GET /api/me/history': () => json(200, page([entry(2), entry(1)])) })
    renderApp('/feed/history')
    expect(await screen.findByRole('heading', { name: 'Watch history' })).toBeInTheDocument()
    const links = await screen.findAllByRole('link', { name: /Video \d/ })
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      '/watch?v=video-00002',
      '/watch?v=video-00001',
    ])
  })

  it('says when there is nothing yet', async () => {
    mockApi({ ...SIGNED_IN, 'GET /api/me/history': () => json(200, page([])) })
    renderApp('/feed/history')
    const main = await screen.findByRole('main')
    expect(await within(main).findByText('Videos you watch appear here.')).toBeInTheDocument()
  })
})
