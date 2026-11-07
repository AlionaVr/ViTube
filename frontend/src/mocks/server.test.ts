import { afterEach, describe, expect, it } from 'vitest'

import { ApiError } from '../api/client'
import {
  addComment,
  getVideo,
  listComments,
  listVideos,
  rateVideo,
  resetMockServer,
  setDemoGuest,
} from './server'

// The contract the UI relies on; the real API should answer the same way.
describe('demo server', () => {
  afterEach(() => {
    resetMockServer()
    localStorage.clear()
  })

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

    setDemoGuest(true)
    await expect(rateVideo(before.id, 'none')).rejects.toBeInstanceOf(ApiError)
  })

  it('lists the viewer’s new comment first', async () => {
    const { items } = await listVideos({ category: null, cursor: null })
    const comment = await addComment(items[0].id, '  Nice!  ', null)
    expect(comment.text).toBe('Nice!')

    const top = await listComments(items[0].id, 'top', null)
    expect(top.items[0].id).toBe(comment.id)
  })
})
