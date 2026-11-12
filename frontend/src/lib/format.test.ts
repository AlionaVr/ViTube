import { describe, expect, it } from 'vitest'

import {
  formatComments,
  formatCompact,
  formatDuration,
  formatTimeAgo,
  formatHistoryDay,
  formatUpdated,
  formatVideoCount,
  formatViews,
  formatViewsExact,
} from './format'

describe('formatCompact', () => {
  it.each([
    [999, '999'],
    [1000, '1K'],
    [1234, '1.2K'],
    [1999, '1.9K'],
    [12_345, '12K'],
    [999_999, '999K'],
    [1_234_567, '1.2M'],
    [12_345_678, '12M'],
    [2_100_000_000, '2.1B'],
  ])('%d → %s', (n, text) => {
    expect(formatCompact(n)).toBe(text)
  })
})

describe('counted labels', () => {
  it('handle zero, one and many', () => {
    expect(formatViews(0)).toBe('No views')
    expect(formatViews(1)).toBe('1 view')
    expect(formatViews(48_213)).toBe('48K views')
    expect(formatViewsExact(1)).toBe('1 view')
    expect(formatViewsExact(48_213)).toBe('48,213 views')
    expect(formatComments(1234)).toBe('1,234 comments')
    expect(formatVideoCount(0)).toBe('No videos')
    expect(formatVideoCount(1)).toBe('1 video')
    expect(formatVideoCount(1234)).toBe('1.2K videos')
  })
})

describe('formatTimeAgo', () => {
  const now = Date.parse('2026-11-07T12:00:00Z')
  const ago = (seconds: number) => formatTimeAgo(new Date(now - seconds * 1000).toISOString(), now)

  it.each([
    [0, 'just now'],
    [1, '1 second ago'],
    [59, '59 seconds ago'],
    [60, '1 minute ago'],
    [2 * 3600, '2 hours ago'],
    [3 * 86_400, '3 days ago'],
    [13 * 86_400, '1 week ago'],
    [45 * 86_400, '1 month ago'],
    [364 * 86_400, '11 months ago'],
    [400 * 86_400, '1 year ago'],
  ])('%ds → %s', (seconds, text) => {
    expect(ago(seconds)).toBe(text)
  })
})

describe('formatDuration', () => {
  it.each([
    [5, '0:05'],
    [52.2, '0:52'],
    [725, '12:05'],
    [3723, '1:02:03'],
  ])('%ds → %s', (seconds, text) => {
    expect(formatDuration(seconds)).toBe(text)
  })
})

describe('formatUpdated', () => {
  // Local time, as the viewer's calendar.
  const now = new Date(2026, 10, 12, 9, 0).getTime()
  const at = (day: number, hour: number) => new Date(2026, 10, day, hour).toISOString()

  it.each([
    [at(12, 0), 'Updated today'],
    [at(11, 23), 'Updated yesterday'], // ten hours ago, but another day
    [at(11, 0), 'Updated yesterday'],
    [at(9, 12), 'Updated 3 days ago'],
    [at(6, 12), 'Updated 6 days ago'],
    [at(1, 12), 'Updated 1 week ago'],
  ])('%s → %s', (iso, text) => {
    expect(formatUpdated(iso, now)).toBe(text)
  })
})

describe('formatHistoryDay', () => {
  // Thursday, Nov 12, 2026, local time.
  const now = new Date(2026, 10, 12, 9, 0).getTime()
  const at = (month: number, day: number, hour = 12, year = 2026) =>
    new Date(year, month, day, hour).toISOString()

  it.each([
    [at(10, 12, 0), 'Today'],
    [at(10, 11, 23), 'Yesterday'],
    [at(10, 9), 'Monday'],
    [at(10, 6), 'Friday'],
    [at(10, 5), 'Nov 5'],
    [at(0, 3), 'Jan 3'],
    [at(11, 30, 12, 2025), 'Dec 30, 2025'],
  ])('%s → %s', (iso, text) => {
    expect(formatHistoryDay(iso, now)).toBe(text)
  })
})
