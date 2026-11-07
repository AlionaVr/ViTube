import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { ApiError } from '../api/client'
import { ANNA, json, mockApi } from '../test/api'
import {
  addComment,
  getVideo,
  listComments,
  listSubscriptions,
  listVideos,
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

  it('pages the feed with a cursor and filters by category', async () => {
    const first = await listVideos({ category: null, cursor: null })
    expect(first.items).toHaveLength(12)
    const second = await listVideos({ category: null, cursor: first.next_cursor })
    expect(second.items[0].id).not.toBe(first.items[0].id)

    const nature = await listVideos({ category: 'nature', cursor: null })
    expect(nature.items.length).toBeGreaterThan(0)
    expect(nature.next_cursor).toBeNull()
  })

  it('answers 404 for an unknown video', async () => {
    await expect(getVideo('nope')).rejects.toMatchObject({ status: 404 })
  })

  it('counts the viewer’s like and refuses a guest', async () => {
    const { items } = await listVideos({ category: null, cursor: null })
    const before = await getVideo(items[0].id)

    const after = await rateVideo(before.id, 'like')
    expect(after).toEqual({ like_count: before.like_count + 1, my_rating: 'like' })

    asGuest()
    await expect(rateVideo(before.id, 'none')).rejects.toBeInstanceOf(ApiError)
  })

  it('lists the viewer’s new comment first, signed with their handle', async () => {
    const { items } = await listVideos({ category: null, cursor: null })
    const comment = await addComment(items[0].id, '  Nice!  ', null)
    expect(comment.text).toBe('Nice!')
    expect(comment.author.handle).toBe(ANNA.handle)

    const top = await listComments(items[0].id, 'top', null)
    expect(top.items[0].id).toBe(comment.id)
  })

  it('answers a guest when there is no auth backend', async () => {
    mockApi({}) // every request fails, as in offline dev
    expect(await listSubscriptions()).toEqual([])
    expect((await listVideos({ category: null, cursor: null })).items).toHaveLength(12)
    await expect(addComment('any', 'Hi', null)).rejects.toMatchObject({ status: 401 })
  })
})
