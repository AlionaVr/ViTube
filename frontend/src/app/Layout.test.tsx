import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { json, mockApi } from '../test/api'
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

  it('shows the signed-in guide by default and the sign-in prompt for a guest', async () => {
    renderApp('/')
    expect(await screen.findByRole('link', { name: 'Liked videos' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Subscriptions' })).toBeInTheDocument()
    expect(screen.queryByText(/Sign in to like videos/)).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'View as a guest' }))
    expect(await screen.findByText(/Sign in to like videos/)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Liked videos' })).not.toBeInTheDocument()
  })

  it('shows the not-found page for unknown paths', () => {
    renderApp('/no-such-page')
    expect(screen.getByText("This page isn't available")).toBeInTheDocument()
  })
})
