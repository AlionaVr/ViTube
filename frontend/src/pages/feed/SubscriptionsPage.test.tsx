import { act, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ANNA, json, mockApi } from '../../test/api'
import { intersectAll } from '../../test/observers'
import { renderApp } from '../../test/render'
import { page, summary } from '../../test/videos'

const SIGNED_IN = { 'GET /api/auth/me': () => json(200, ANNA) }
const NO_SUBSCRIPTIONS = { 'GET /api/me/subscriptions': () => json(200, page([])) }
const main = () => screen.getByRole('main')

describe('SubscriptionsPage', () => {
  it('shows the newest videos of the viewer’s subscriptions', async () => {
    mockApi({
      ...SIGNED_IN,
      ...NO_SUBSCRIPTIONS,
      'GET /api/feed/subscriptions': () => json(200, page([summary(1), summary(2)])),
    })
    renderApp('/feed/subscriptions')

    expect(await screen.findByRole('heading', { name: 'Latest' })).toBeInTheDocument()
    expect(within(main()).getByRole('link', { name: 'Manage' })).toHaveAttribute(
      'href',
      '/feed/channels',
    )
    expect(await within(main()).findByRole('link', { name: 'Video 1' })).toBeInTheDocument()
    expect(within(main()).getAllByRole('link', { name: 'Open Movie Club' })).toHaveLength(2)
    expect(screen.getByRole('link', { name: 'Subscriptions' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('loads the next page on scroll', async () => {
    mockApi({
      ...SIGNED_IN,
      ...NO_SUBSCRIPTIONS,
      'GET /api/feed/subscriptions': (request) =>
        new URL(request.url).searchParams.get('cursor') === 'next'
          ? json(200, page([summary(2)]))
          : json(200, page([summary(1)], 'next')),
    })
    renderApp('/feed/subscriptions')
    await within(main()).findByRole('link', { name: 'Video 1' })

    act(() => intersectAll())

    expect(await within(main()).findByRole('link', { name: 'Video 2' })).toBeInTheDocument()
  })

  it('says so when there is nothing new', async () => {
    mockApi({
      ...SIGNED_IN,
      ...NO_SUBSCRIPTIONS,
      'GET /api/feed/subscriptions': () => json(200, page([])),
    })
    renderApp('/feed/subscriptions')

    expect(await screen.findByRole('heading', { name: 'No new videos' })).toBeInTheDocument()
  })

  it('asks a guest to sign in', async () => {
    mockApi({ 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) })
    renderApp('/feed/subscriptions')

    expect(
      await screen.findByRole('heading', { name: 'Don’t miss new videos' }),
    ).toBeInTheDocument()
  })
})
