import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ANNA, json, mockApi } from '../test/api'
import { renderApp } from '../test/render'

const signedIn = () =>
  mockApi({
    'GET /api/auth/me': () => json(200, ANNA),
    'POST /api/auth/logout': () => new Response(null, { status: 204 }),
  })

const header = () => within(screen.getByRole('banner'))

async function openMenu() {
  await userEvent.click(await screen.findByRole('button', { name: 'Account menu' }))
}

describe('header account area', () => {
  it('offers sign in to a guest and keeps the page to come back to', async () => {
    mockApi({ 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) })
    const router = renderApp('/results?search_query=cats')

    await userEvent.click(await header().findByRole('link', { name: 'Sign in' }))

    expect(router.state.location.pathname).toBe('/login')
    expect(router.state.location.state).toEqual({ from: '/results?search_query=cats' })
  })

  it('shows the signed-in account', async () => {
    signedIn()
    renderApp('/')

    await openMenu()

    expect(screen.getByText(ANNA.email)).toBeInTheDocument()
    expect(screen.getByText(`@${ANNA.handle}`)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Sign in' })).not.toBeInTheDocument()
  })

  it('leads moderators to the moderation page', async () => {
    mockApi({ 'GET /api/auth/me': () => json(200, { ...ANNA, role: 'moderator' }) })
    const router = renderApp('/')
    await openMenu()
    const signOut = screen.getByRole('button', { name: 'Sign out' })
    const moderation = screen.getByRole('link', { name: 'Moderation' })
    // Its own group after Sign out, as YouTube Studio's link is.
    expect(signOut.compareDocumentPosition(moderation)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)

    await userEvent.click(moderation)

    expect(router.state.location.pathname).toBe('/moderation')
  })

  it('shows no moderation link to other users', async () => {
    signedIn()
    renderApp('/')

    await openMenu()

    expect(screen.queryByRole('link', { name: 'Moderation' })).not.toBeInTheDocument()
  })

  it('signs out', async () => {
    const fetch = signedIn()
    renderApp('/')
    await openMenu()

    await userEvent.click(screen.getByRole('button', { name: 'Sign out' }))

    expect(await header().findByRole('link', { name: 'Sign in' })).toBeInTheDocument()
    expect(fetch.mock.calls.some(([request]) => request.method === 'POST')).toBe(true)
  })

  it('closes on Escape and gives focus back to the avatar', async () => {
    signedIn()
    renderApp('/')
    await openMenu()
    const avatar = screen.getByRole('button', { name: 'Account menu' })
    expect(avatar).toHaveAttribute('aria-expanded', 'true')

    await userEvent.keyboard('{Escape}')

    expect(avatar).toHaveAttribute('aria-expanded', 'false')
    expect(avatar).toHaveFocus()
    expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument()
  })

  it('closes on a click outside', async () => {
    signedIn()
    renderApp('/')
    await openMenu()

    await userEvent.click(screen.getByRole('main'))

    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument(),
    )
  })
})
