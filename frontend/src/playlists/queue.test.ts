import { describe, expect, it } from 'vitest'

import { summary } from '../test/videos'
import { inOrder, inShuffle, shuffled } from './queue'

const VIDEOS = [1, 2, 3].map((n) => summary(n))

describe('inOrder', () => {
  it('goes to the video after the current one', () => {
    expect(inOrder(VIDEOS, 'video-00002', true)).toEqual({
      position: 1,
      next: { status: 'video', video: VIDEOS[2] },
    })
  })

  it('ends after the last video of the whole list', () => {
    expect(inOrder(VIDEOS, 'video-00003', true)).toEqual({ position: 2, next: { status: 'end' } })
  })

  it('waits for the next page after the last loaded video', () => {
    expect(inOrder(VIDEOS, 'video-00003', false)).toEqual({
      position: 2,
      next: { status: 'pending' },
    })
  })

  it('waits for more pages while the current video isn’t loaded', () => {
    expect(inOrder(VIDEOS, 'video-00009', false)).toEqual({
      position: null,
      next: { status: 'pending' },
    })
  })

  it('starts from the top after a video that isn’t in the list', () => {
    expect(inOrder(VIDEOS, 'video-00009', true)).toEqual({
      position: null,
      next: { status: 'video', video: VIDEOS[0] },
    })
  })

  it('ends an empty list at once', () => {
    expect(inOrder([], 'video-00001', true)).toEqual({ position: null, next: { status: 'end' } })
  })
})

const TEN = Array.from({ length: 10 }, (_, n) => summary(n + 1))
const ids = (videos: { id: string }[]) => videos.map((video) => video.id)

describe('shuffled', () => {
  it('mixes the videos the same way for the same seed, and another way for another', () => {
    const once = ids(shuffled(TEN, 'seed-a'))

    expect(ids(shuffled(TEN, 'seed-a'))).toEqual(once)
    expect(ids(shuffled(TEN, 'seed-b'))).not.toEqual(once)
    expect(once).not.toEqual(ids(TEN))
    expect([...once].sort()).toEqual(ids(TEN))
  })

  it('keeps the others in their places when a video leaves', () => {
    const all = ids(shuffled(TEN, 'seed-a'))
    const without = ids(shuffled(TEN.slice(1), 'seed-a'))

    expect(without).toEqual(all.filter((id) => id !== TEN[0].id))
  })
})

describe('inShuffle', () => {
  it('starts at the current video and plays every other once, then ends', () => {
    const played = [TEN[4].id]
    let step = inShuffle(TEN, TEN[4].id, 'seed-a', 1)
    expect(step.position).toBe(0)
    while (step.next.status === 'video') {
      const id = step.next.video.id
      played.push(id)
      step = inShuffle(TEN, id, 'seed-a', played.length)
      // The order holds still while it plays.
      expect(ids(step.videos)).toEqual(played.concat(ids(step.videos).slice(played.length)))
    }

    expect(step.next.status).toBe('end')
    expect([...played].sort()).toEqual(ids(TEN))
  })

  it('takes an index it can’t use as the start', () => {
    for (const index of [0, 11, Number.NaN]) {
      expect(inShuffle(TEN, TEN[4].id, 'seed-a', index).videos[0]).toBe(TEN[4])
    }
  })

  it('starts the order after a video that isn’t on the first page', () => {
    const order = shuffled(TEN, 'seed-a')

    expect(inShuffle(TEN, 'video-00099', 'seed-a', 1)).toEqual({
      videos: order,
      position: null,
      next: { status: 'video', video: order[0] },
    })
  })
})
