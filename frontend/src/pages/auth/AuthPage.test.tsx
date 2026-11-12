import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ANNA, json, mockApi } from '../../test/api'
import { renderApp } from '../../test/render'

const guest = () => json(401, { detail: 'Sign in required' })

async function fillIn(email: string, password: string) {
  if (email) await userEvent.type(screen.getByLabelText('Email'), email)
  if (password) await userEvent.type(screen.getByLabelText('Password'), password)
}

const submit = (name: string) => userEvent.click(screen.getByRole('button', { name }))

describe('sign in page', () => {
  it('signs in and goes back to the page the user came from', async () => {
    const fetch = mockApi({
      'GET /api/auth/me': guest,
      'POST /api/auth/login': () => json(200, ANNA),
    })
    const router = renderApp('/login', { from: '/results?search_query=cats' })

    await fillIn(' anna@example.com ', 'correct horse')
    await submit('Sign in')

    await waitFor(() => expect(router.state.location.pathname).toBe('/results'))
    expect(router.state.location.search).toBe('?search_query=cats')
    const login = fetch.mock.calls.map(([request]) => request).find((r) => r.method === 'POST')
    expect(await login?.json()).toEqual({ email: 'anna@example.com', password: 'correct horse' })
  })

  it('asks for both fields before sending anything', async () => {
    const fetch = mockApi({ 'GET /api/auth/me': guest })
    renderApp('/login')

    await submit('Sign in')

    expect(await screen.findByText('Enter an email')).toBeInTheDocument()
    expect(screen.getByText('Enter a password')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveFocus()
    expect(fetch.mock.calls.every(([request]) => request.method === 'GET')).toBe(true)
  })

  it('shows a wrong password under the password field', async () => {
    mockApi({
      'GET /api/auth/me': guest,
      'POST /api/auth/login': () => json(401, { detail: 'Wrong email or password' }),
    })
    renderApp('/login')

    await fillIn('anna@example.com', 'wrong password')
    await submit('Sign in')

    const password = screen.getByLabelText('Password')
    await waitFor(() => expect(password).toHaveAttribute('aria-invalid', 'true'))
    expect(password).toHaveAccessibleDescription('Wrong email or password. Try again.')
  })

  it('tells the user to wait after too many attempts', async () => {
    mockApi({
      'GET /api/auth/me': guest,
      'POST /api/auth/login': () => json(429, { detail: 'Too many attempts. Try again later.' }),
    })
    renderApp('/login')

    await fillIn('anna@example.com', 'whatever-1')
    await submit('Sign in')

    expect(await screen.findByRole('alert')).toHaveTextContent('Too many attempts. Wait a few')
  })

  it('says why a banned account cannot sign in', async () => {
    mockApi({
      'GET /api/auth/me': guest,
      'POST /api/auth/login': () => json(403, { detail: 'This account is banned' }),
    })
    renderApp('/login')

    await fillIn('anna@example.com', 'correct horse battery')
    await submit('Sign in')

    expect(await screen.findByText('This account is banned')).toBeInTheDocument()
  })

  it('says when the server is out of reach', async () => {
    mockApi({
      'GET /api/auth/me': guest,
      'POST /api/auth/login': () => Promise.reject(new TypeError('Failed to fetch')),
    })
    renderApp('/login')

    await fillIn('anna@example.com', 'whatever-1')
    await submit('Sign in')

    expect(await screen.findByRole('alert')).toHaveTextContent("Can't reach ViTube")
  })

  it('shows the password on request', async () => {
    mockApi({ 'GET /api/auth/me': guest })
    renderApp('/login')
    const password = screen.getByLabelText('Password')
    expect(password).toHaveAttribute('type', 'password')

    await userEvent.click(screen.getByLabelText('Show password'))

    expect(password).toHaveAttribute('type', 'text')
  })

  it('sends a signed-in user on to the home page', async () => {
    mockApi({ 'GET /api/auth/me': () => json(200, ANNA) })
    const router = renderApp('/login')

    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
  })
})

describe('sign up page', () => {
  it('creates the account and signs in', async () => {
    mockApi({
      'GET /api/auth/me': guest,
      'POST /api/auth/signup': () => json(201, ANNA),
    })
    const router = renderApp('/signup')

    await fillIn('anna@example.com', 'correct horse')
    await submit('Create account')

    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
  })

  it('checks the password length before sending', async () => {
    const fetch = mockApi({ 'GET /api/auth/me': guest })
    renderApp('/signup')
    expect(screen.getByLabelText('Password')).toHaveAccessibleDescription(
      'Use 8 or more characters',
    )

    await fillIn('anna@example.com', 'short')
    await submit('Create account')

    expect(screen.getByLabelText('Password')).toHaveAccessibleDescription(
      'Use 8 characters or more for your password',
    )
    expect(fetch.mock.calls.every(([request]) => request.method === 'GET')).toBe(true)
  })

  it('points to sign in when the email is taken', async () => {
    mockApi({
      'GET /api/auth/me': guest,
      'POST /api/auth/signup': () => json(409, { detail: 'This email is already registered' }),
    })
    renderApp('/signup')

    await fillIn('anna@example.com', 'correct horse')
    await submit('Create account')

    await waitFor(() =>
      expect(screen.getByLabelText('Email')).toHaveAccessibleDescription(
        'This email is already registered. Sign in instead.',
      ),
    )
    expect(screen.getByRole('link', { name: 'Sign in instead' })).toHaveAttribute('href', '/login')
  })
})

describe('sign in with Google', () => {
  it('offers Google when the server has it on', async () => {
    mockApi({
      'GET /api/auth/me': guest,
      'GET /api/auth/providers': () => json(200, { google: true }),
    })
    renderApp('/signup')

    const google = await screen.findByRole('link', { name: 'Sign up with Google' })
    expect(google).toHaveAttribute('href', '/api/auth/google/start')
  })

  it('shows no Google button while it is off', async () => {
    const fetch = mockApi({
      'GET /api/auth/me': guest,
      'GET /api/auth/providers': () => json(200, { google: false }),
    })
    renderApp('/login')

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Google/ })).not.toBeInTheDocument()
  })
})
