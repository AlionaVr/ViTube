import { describe, expect, it } from 'vitest'

import { summary } from '../test/videos'
import { inOrder } from './queue'

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
