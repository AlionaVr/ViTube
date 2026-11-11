import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { ApiError } from '../api/client'
import { ANNA, json, mockApi } from '../test/api'
import {
  addComment,
  demoVideoId,
  getVideo,
  listComments,
  listSubscriptions,
  rateVideo,
  resetMockServer,
} from './server'

const asGuest = () =>
  mockApi({ 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) })

// The contract the UI relies on; the real API should answer the same way.
describe('demo server', () => {
  beforeEach(() => {
    mockApi({ 'GET /api/auth/me': () => json(200, ANNA) })
  })
  afterEach(() => resetMockServer())

  it('answers 404 for an unknown video', async () => {
    await expect(getVideo('nope')).rejects.toMatchObject({ status: 404 })
  })

  it('counts the viewer’s like and refuses a guest', async () => {
    const before = await getVideo(demoVideoId('Sintel – trailer'))

    const after = await rateVideo(before.id, 'like')
    expect(after).toEqual({ like_count: before.like_count + 1, my_rating: 'like' })

    asGuest()
    await expect(rateVideo(before.id, 'none')).rejects.toBeInstanceOf(ApiError)
  })

  it('lists the viewer’s new comment first, signed with their handle', async () => {
    const id = demoVideoId('Sintel – trailer')
    const comment = await addComment(id, '  Nice!  ', null)
    expect(comment.text).toBe('Nice!')
    expect(comment.author.handle).toBe(ANNA.handle)

    const top = await listComments(id, 'top', null)
    expect(top.items[0].id).toBe(comment.id)
  })

  it('answers a guest when there is no auth backend', async () => {
    mockApi({}) // every request fails, as in offline dev
    expect(await listSubscriptions()).toEqual([])
    await expect(addComment('any', 'Hi', null)).rejects.toMatchObject({ status: 401 })
  })
})
