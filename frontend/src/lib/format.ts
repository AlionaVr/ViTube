// Numbers and dates the way YouTube shows them (English UI).

// YouTube truncates: 1,999 views is "1.9K", not "2K".
const compact = new Intl.NumberFormat('en', { notation: 'compact', roundingMode: 'trunc' })
const exact = new Intl.NumberFormat('en')
const date = new Intl.DateTimeFormat('en', { dateStyle: 'medium' })
const weekday = new Intl.DateTimeFormat('en', { weekday: 'long' })
const monthDay = new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric' })

/** 1234 → "1.2K", 12345 → "12K", 1234567 → "1.2M". */
export function formatCompact(n: number): string {
  return compact.format(n)
}

/** 1234 → "1,234". */
export function formatExact(n: number): string {
  return exact.format(n)
}

function counted(n: number, one: string, many: string, format: (n: number) => string): string {
  if (n === 0) return `No ${many}`
  return n === 1 ? `1 ${one}` : `${format(n)} ${many}`
}

/** "No views", "1 view", "1.2K views". */
export function formatViews(n: number): string {
  return counted(n, 'view', 'views', formatCompact)
}

/** "No views", "1 view", "1,234 views": the expanded description. */
export function formatViewsExact(n: number): string {
  return counted(n, 'view', 'views', formatExact)
}

/** "1 subscriber", "1.2M subscribers". */
export function formatSubscribers(n: number): string {
  return counted(n, 'subscriber', 'subscribers', formatCompact)
}

/** "No videos", "1 video", "1.2K videos": a channel's count. */
export function formatVideoCount(n: number): string {
  return counted(n, 'video', 'videos', formatCompact)
}

/** "1 comment", "1,234 comments". */
export function formatComments(n: number): string {
  return counted(n, 'comment', 'comments', formatExact)
}

const UNITS: [unit: string, seconds: number][] = [
  ['year', 365 * 24 * 3600],
  // A twelfth of a year: 30 days would give "12 months ago" for 360–364 days.
  ['month', (365 / 12) * 24 * 3600],
  ['week', 7 * 24 * 3600],
  ['day', 24 * 3600],
  ['hour', 3600],
  ['minute', 60],
  ['second', 1],
]

/** "3 days ago", "1 month ago". */
export function formatTimeAgo(iso: string, now = Date.now()): string {
  const seconds = Math.max(0, Math.floor((now - Date.parse(iso)) / 1000))
  for (const [unit, size] of UNITS) {
    const count = Math.floor(seconds / size)
    if (count >= 1) return `${count} ${unit}${count === 1 ? '' : 's'} ago`
  }
  return 'just now'
}

const DAY_MS = 86_400_000

/** Calendar days on the viewer's clock from `iso` to `now`: 0 today, 1 yesterday. */
function daysBefore(iso: string, now: number): number {
  const midnight = (time: number) => new Date(time).setHours(0, 0, 0, 0)
  // Rounded: a day with a clock change is 23 or 25 hours long.
  return Math.round((midnight(now) - midnight(Date.parse(iso))) / DAY_MS)
}

/** A playlist's change, in calendar days as YouTube counts them: "Updated today", "Updated
 * yesterday", "Updated 3 days ago"; from a week on, "Updated 2 weeks ago" and so on. */
export function formatUpdated(iso: string, now = Date.now()): string {
  const days = daysBefore(iso, now)
  if (days <= 0) return 'Updated today'
  if (days === 1) return 'Updated yesterday'
  if (days < 7) return `Updated ${days} days ago`
  return `Updated ${formatTimeAgo(iso, now)}`
}

/** A day of the watch history, as YouTube heads it: "Today", "Yesterday", "Monday" within a
 * week, then "Nov 3", with the year if it isn't this one. */
export function formatHistoryDay(iso: string, now = Date.now()): string {
  const days = daysBefore(iso, now)
  if (days <= 0) return 'Today'
  if (days === 1) return 'Yesterday'
  const day = new Date(iso)
  if (days < 7) return weekday.format(day)
  return day.getFullYear() === new Date(now).getFullYear() ? monthDay.format(day) : date.format(day)
}

/** "Nov 7, 2026". */
export function formatDate(iso: string): string {
  return date.format(new Date(iso))
}

/** 5 → "0:05", 725 → "12:05", 3723 → "1:02:03". */
export function formatDuration(totalSeconds: number): string {
  const total = Math.floor(totalSeconds)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = String(total % 60).padStart(2, '0')
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, '0')}:${seconds}`
    : `${minutes}:${seconds}`
}
