import { describe, expect, it } from 'vitest'

import { formatLength, formatLimits, formatSize } from './format'

describe('upload limits in words', () => {
  it('names sizes as the server counts them', () => {
    expect(formatSize(1024 ** 3)).toBe('1 GB')
    expect(formatSize(2 * 1024 ** 3)).toBe('2 GB')
    expect(formatSize(500 * 1024 ** 2)).toBe('500 MB')
  })

  it('names lengths in minutes when they are whole', () => {
    expect(formatLength(1800)).toBe('30 minutes')
    expect(formatLength(60)).toBe('1 minute')
    expect(formatLength(90)).toBe('90 seconds')
  })

  it('puts both into one line', () => {
    expect(formatLimits({ max_size_bytes: 1024 ** 3, max_duration_sec: 1800 })).toBe(
      'Up to 1 GB and 30 minutes',
    )
  })
})
