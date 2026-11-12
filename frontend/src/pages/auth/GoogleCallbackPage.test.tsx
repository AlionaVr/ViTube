import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { rememberReturnPath } from '../../auth/returnPath'
import { ANNA, json, mockApi } from '../../test/api'
import { renderApp } from '../../test/render'

const guest = () => json(401, { detail: 'Sign in required' })
const CALLBACK = '/auth/google/callback?code=test-code&state=test-state'

afterEach(() => sessionStorage.clear())

describe('Google callback page', () => {
  it('finishes signing in and goes back to the page the user came from', async () => {
    rememberReturnPath('/watch?v=abc')
    const fetch = mockApi({
      'GET /api/auth/me': guest,
      'GET /api/auth/providers': () => json(200, { google: true }),
      'POST /api/auth/google/finish': () => json(200, ANNA),
    })
    const router = renderApp(CALLBACK)

    await waitFor(() => expect(router.state.location.pathname).toBe('/watch'))
    expect(router.state.location.search).toBe('?v=abc')
    const finishes = fetch.mock.calls.map(([request]) => request).filter((r) => r.method === 'POST')
    expect(finishes).toHaveLength(1)
    expect(await finishes[0].text()).toBe('code=test-code&state=test-state')
  })

  it('goes back to sign in with the reason when the email is taken', async () => {
    const taken = 'This email is already registered with another sign-in method.'
    mockApi({
      'GET /api/auth/me': guest,
      'GET /api/auth/providers': () => json(200, { google: true }),
      'POST /api/auth/google/finish': () => json(409, { detail: taken }),
    })
    const router = renderApp(CALLBACK)

    expect(await screen.findByRole('alert')).toHaveTextContent(taken)
    expect(router.state.location.pathname).toBe('/login')
  })

  it('goes back to sign in quietly when the user cancels at Google', async () => {
    const fetch = mockApi({
      'GET /api/auth/me': guest,
      'GET /api/auth/providers': () => json(200, { google: true }),
    })
    const router = renderApp('/auth/google/callback?error=access_denied&state=test-state')

    expect(await screen.findByRole('link', { name: 'Sign in with Google' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(fetch.mock.calls.every(([request]) => request.method === 'GET')).toBe(true)
  })

  it('takes only a page of this site as the way back', async () => {
    rememberReturnPath('//evil.example/phish')
    mockApi({
      'GET /api/auth/me': guest,
      'GET /api/auth/providers': () => json(200, { google: true }),
      'POST /api/auth/google/finish': () => json(200, ANNA),
      'GET /api/videos': () => json(200, { items: [], next_cursor: null }),
    })
    const router = renderApp(CALLBACK)

    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
  })
})
