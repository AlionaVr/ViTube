import { describe, expect, it } from 'vitest'

import { ANNA, json, mockApi } from '../test/api'
import { listSubscriptions } from './server'

// The contract the sidebar relies on; the real API should answer the same way.
describe('demo server', () => {
  it('lists subscriptions for a signed-in viewer', async () => {
    mockApi({ 'GET /api/auth/me': () => json(200, ANNA) })
    expect((await listSubscriptions()).map((c) => c.handle)).toContain('framebyframe')
  })

  it('answers a guest, also when there is no auth backend', async () => {
    mockApi({ 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) })
    expect(await listSubscriptions()).toEqual([])
    mockApi({}) // every request fails, as in offline dev
    expect(await listSubscriptions()).toEqual([])
  })
})
