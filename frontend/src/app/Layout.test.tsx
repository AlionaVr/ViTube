import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { ANNA, json, mockApi } from '../test/api'
import { channel } from '../test/channels'
import { renderApp } from '../test/render'
import { setScreenWidth } from '../test/screen'

const menuButton = () => screen.getAllByRole('button', { name: 'Menu' })[0]

describe('Layout', () => {
  beforeEach(() => {
    mockApi({ 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) })
  })
  afterEach(() => localStorage.clear())

  it('collapses the sidebar to mini mode and back on wide screens', async () => {
    renderApp('/')
    const menu = menuButton()
    expect(menu).toHaveAttribute('aria-expanded', 'true')
    expect(await screen.findByRole('link', { name: 'History' })).toBeInTheDocument()

    await userEvent.click(menu)
    expect(menu).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('link', { name: 'History' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Home' })).toHaveAttribute('aria-current', 'page')

    await userEvent.click(menu)
    expect(menu).toHaveAttribute('aria-expanded', 'true')
  })

  it('remembers a collapsed guide after a reload', async () => {
    renderApp('/')
    await userEvent.click(menuButton())
    cleanup()

    renderApp('/')
    expect(menuButton()).toHaveAttribute('aria-expanded', 'false')
  })

  it('opens the guide as a drawer on narrower screens and closes it on the scrim', async () => {
    setScreenWidth(1000)
    renderApp('/')
    const menu = menuButton()
    expect(menu).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await userEvent.click(menu)
    const drawer = screen.getByRole('dialog', { name: 'Guide' })
    expect(menu).toHaveAttribute('aria-expanded', 'true')
    expect(await within(drawer).findByRole('link', { name: 'History' })).toBeInTheDocument()

    fireEvent.click(drawer) // a click on the backdrop targets the dialog itself
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(menu).toHaveAttribute('aria-expanded', 'false')
  })

  it('closes the drawer when a link in it is followed', async () => {
    setScreenWidth(700)
    const router = renderApp('/')

    await userEvent.click(menuButton())
    const drawer = screen.getByRole('dialog', { name: 'Guide' })
    await userEvent.click(await within(drawer).findByRole('link', { name: 'History' }))

    expect(router.state.location.pathname).toBe('/feed/history')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('shows the library, subscriptions and account menu to a signed-in viewer', async () => {
    const anna = { handle: 'anna', name: 'Anna', avatar_url: null, subscriber_count: 3 }
    mockApi({
      'GET /api/auth/me': () => json(200, ANNA),
      'GET /api/me/subscriptions': () => json(200, { items: [anna], next_cursor: null }),
    })
    renderApp('/')
    expect(await screen.findByRole('button', { name: 'Account menu' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Liked videos' })).toBeInTheDocument()
    const heading = await screen.findByRole('heading', { name: 'Subscriptions' })
    expect(within(heading).getByRole('link')).toHaveAttribute('href', '/feed/channels')
    expect(screen.getByRole('link', { name: 'Anna' })).toHaveAttribute('href', '/@anna')
    expect(screen.queryByText(/Sign in to like videos/)).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Sign in' })).not.toBeInTheDocument()
  })

  it('shows seven subscriptions in the guide, the rest on Show more', async () => {
    const subscriptions = Array.from({ length: 9 }, (_, i) => ({
      handle: `channel${i + 1}`,
      name: `Channel ${i + 1}`,
      avatar_url: null,
      subscriber_count: 1,
    }))
    mockApi({
      'GET /api/auth/me': () => json(200, ANNA),
      'GET /api/me/subscriptions': () => json(200, { items: subscriptions, next_cursor: null }),
    })
    renderApp('/')
    const guide = within(await screen.findByRole('navigation', { name: 'Main' }))
    await guide.findByRole('link', { name: 'Channel 1' })

    expect(guide.getByRole('link', { name: 'Channel 7' })).toBeInTheDocument()
    expect(guide.queryByRole('link', { name: 'Channel 8' })).not.toBeInTheDocument()
    await userEvent.click(guide.getByRole('button', { name: 'Show 2 more' }))
    expect(guide.getByRole('link', { name: 'Channel 9' })).toBeInTheDocument()
    await userEvent.click(guide.getByRole('button', { name: 'Show fewer' }))
    expect(guide.queryByRole('link', { name: 'Channel 9' })).not.toBeInTheDocument()
  })

  it('marks the open channel in the guide, whatever the case of its URL', async () => {
    const anna = { handle: 'anna', name: 'Anna', avatar_url: null, subscriber_count: 3 }
    mockApi({
      'GET /api/auth/me': () => json(200, ANNA),
      'GET /api/me/subscriptions': () => json(200, { items: [anna], next_cursor: null }),
      'GET /api/channels/ANNA': () => json(200, channel({ handle: 'anna', name: 'Anna' })),
      'GET /api/channels/ANNA/videos': () => json(200, { items: [], next_cursor: null }),
    })
    renderApp('/@ANNA/videos')
    const guide = within(await screen.findByRole('navigation', { name: 'Main' }))

    expect(await guide.findByRole('link', { name: 'Anna' })).toHaveAttribute('aria-current', 'page')
  })

  it('shows the sign-in prompt and button to a guest', async () => {
    renderApp('/')
    expect(await screen.findByText(/Sign in to like videos/)).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Sign in' })).toHaveLength(2)
    expect(screen.queryByRole('link', { name: 'Liked videos' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Account menu' })).not.toBeInTheDocument()
  })

  it('shows the not-found page for unknown paths', () => {
    renderApp('/no-such-page')
    expect(screen.getByText("This page isn't available")).toBeInTheDocument()
  })
})
