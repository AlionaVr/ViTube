import type { User } from '../api/client'
import styles from './Avatar.module.css'

// A channel without a picture gets its first letter on a color, as on YouTube.
const COLORS = [
  '#c2185b',
  '#7b1fa2',
  '#512da8',
  '#1976d2',
  '#0097a7',
  '#00796b',
  '#388e3c',
  '#e64a19',
]

function colorOf(seed: string): string {
  let hash = 0
  for (const char of seed) hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  return COLORS[hash % COLORS.length]
}

export default function Avatar({ user, size }: { user: User; size: number }) {
  return (
    <span
      className={styles.avatar}
      style={{ width: size, height: size, fontSize: size / 2, background: colorOf(user.handle) }}
      aria-hidden="true"
    >
      {user.email[0].toUpperCase()}
    </span>
  )
}
