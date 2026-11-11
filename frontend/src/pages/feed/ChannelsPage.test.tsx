import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import type { SubscribedChannel } from '../../channels/types'
import { ANNA, json, mockApi } from '../../test/api'
import { intersectAll } from '../../test/observers'
import { renderApp } from '../../test/render'

const SIGNED_IN = { 'GET /api/auth/me': () => json(200, ANNA) }

function subscribed(handle: string, subscriber_count = 1): SubscribedChannel {
  return { handle, name: handle.toUpperCase(), avatar_url: null, subscriber_count }
}

const main = () => screen.getByRole('main')

describe('ChannelsPage', () => {
  it('lists the viewer’s subscriptions with their counts', async () => {
    mockApi({
      ...SIGNED_IN,
      'GET /api/me/subscriptions': () =>
        json(200, { items: [subscribed('anna'), subscribed('bob', 1200)], next_cursor: null }),
    })
    renderApp('/feed/channels')

    expect(await screen.findByRole('heading', { name: 'All subscriptions' })).toBeInTheDocument()
    const list = await within(main()).findByRole('list')
    expect(within(list).getAllByRole('listitem')).toHaveLength(2)
    expect(within(list).getByRole('link', { name: 'ANNA' })).toHaveAttribute('href', '/@anna')
    expect(within(list).getByText('@bob • 1.2K subscribers')).toBeInTheDocument()
    expect(within(list).getAllByRole('button', { name: /Subscribed/ })).toHaveLength(2)
    expect(document.title).toBe('All subscriptions - ViTube')
  })

  it('drops a channel at once when the viewer unsubscribes', async () => {
    let deleted = false
    const fetch = mockApi({
      ...SIGNED_IN,
      'GET /api/me/subscriptions': () =>
        json(200, {
          items: deleted ? [subscribed('bob')] : [subscribed('anna'), subscribed('bob')],
          next_cursor: null,
        }),
      'DELETE /api/channels/anna/subscription': () => {
        deleted = true
        return json(200, { subscriber_count: 0, is_subscribed: false })
      },
    })
    renderApp('/feed/channels')
    const list = await within(main()).findByRole('list')
    const row = within(list).getByRole('link', { name: 'ANNA' }).closest('li')!

    await userEvent.click(within(row).getByRole('button', { name: /Subscribed/ }))
    await userEvent.click(screen.getByRole('menuitem', { name: 'Unsubscribe' }))
    await userEvent.click(
      within(screen.getByRole('dialog', { name: 'Unsubscribe' })).getByRole('button', {
        name: 'Unsubscribe',
      }),
    )

    await waitFor(() => expect(within(list).queryByText('ANNA')).not.toBeInTheDocument())
    expect(within(list).getByText('BOB')).toBeInTheDocument()
    expect(fetch.mock.calls.some(([request]) => request.method === 'DELETE')).toBe(true)
  })

  it('loads the next page on scroll', async () => {
    mockApi({
      ...SIGNED_IN,
      'GET /api/me/subscriptions': (request) =>
        new URL(request.url).searchParams.get('cursor') === 'next'
          ? json(200, { items: [subscribed('bob')], next_cursor: null })
          : json(200, { items: [subscribed('anna')], next_cursor: 'next' }),
    })
    renderApp('/feed/channels')
    const list = await within(main()).findByRole('list')
    await within(list).findByText('ANNA')

    act(() => intersectAll())

    expect(await within(list).findByText('BOB')).toBeInTheDocument()
  })

  it('invites to subscribe when there are no subscriptions', async () => {
    mockApi({
      ...SIGNED_IN,
      'GET /api/me/subscriptions': () => json(200, { items: [], next_cursor: null }),
    })
    renderApp('/feed/channels')

    expect(await screen.findByRole('heading', { name: 'No subscriptions yet' })).toBeInTheDocument()
  })

  it('asks a guest to sign in', async () => {
    mockApi({ 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) })
    renderApp('/feed/channels')

    expect(
      await screen.findByRole('heading', { name: 'Don’t miss new videos' }),
    ).toBeInTheDocument()
    expect(within(main()).getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
  })
})
