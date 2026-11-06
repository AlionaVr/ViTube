// Numbers and dates the way YouTube shows them (English UI).

// YouTube truncates: 1,999 views is "1.9K", not "2K".
const compact = new Intl.NumberFormat('en', { notation: 'compact', roundingMode: 'trunc' })
const exact = new Intl.NumberFormat('en')
const date = new Intl.DateTimeFormat('en', { dateStyle: 'medium' })

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

/** "1 subscriber", "1.2M subscribers". */
export function formatSubscribers(n: number): string {
  return counted(n, 'subscriber', 'subscribers', formatCompact)
}

/** "1 comment", "1,234 comments". */
export function formatComments(n: number): string {
  return counted(n, 'comment', 'comments', formatExact)
}

const UNITS: [unit: string, seconds: number][] = [
  ['year', 365 * 24 * 3600],
  ['month', 30 * 24 * 3600],
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
