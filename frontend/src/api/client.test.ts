import { afterEach, describe, expect, it } from 'vitest'

import { json, mockApi } from '../test/api'
import { api, unwrap } from './client'

const credentials = { email: 'anna@example.com', password: 'correct horse battery' }

describe('api client', () => {
  afterEach(() => {
    document.cookie = 'csrf_token=; max-age=0'
  })

  it('sends the CSRF token on unsafe requests only', async () => {
    document.cookie = 'csrf_token=token-123'
    const fetch = mockApi({
      'POST /api/auth/logout': () => new Response(null, { status: 204 }),
      'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }),
    })

    await api.POST('/api/auth/logout')
    await api.GET('/api/auth/me')

    const [post, get] = fetch.mock.calls.map(([request]) => request)
    expect(post.headers.get('X-CSRF-Token')).toBe('token-123')
    expect(get.headers.has('X-CSRF-Token')).toBe(false)
  })

  it('sends no CSRF header without a session', async () => {
    const fetch = mockApi({ 'POST /api/auth/logout': () => new Response(null, { status: 204 }) })

    await api.POST('/api/auth/logout')

    expect(fetch.mock.calls[0][0].headers.has('X-CSRF-Token')).toBe(false)
  })

  it('throws ApiError with the server message', async () => {
    mockApi({
      'POST /api/auth/signup': () => json(409, { detail: 'This email is already registered' }),
    })

    await expect(unwrap(api.POST('/api/auth/signup', { body: credentials }))).rejects.toMatchObject(
      { status: 409, message: 'This email is already registered' },
    )
  })

  it('takes the first message of an input error', async () => {
    mockApi({
      'POST /api/auth/signup': () =>
        json(422, { detail: [{ loc: ['body', 'password'], msg: 'Too short', type: 'x' }] }),
    })

    await expect(unwrap(api.POST('/api/auth/signup', { body: credentials }))).rejects.toMatchObject(
      { status: 422, message: 'Too short' },
    )
  })
})
