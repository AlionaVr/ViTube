import styles from './Avatar.module.css'

// YouTube's default avatar: the first letter on a color picked from the name.
const COLORS = [
  '#ef6c00',
  '#00897b',
  '#5e35b1',
  '#c2185b',
  '#1e88e5',
  '#7cb342',
  '#f4511e',
  '#8d6e63',
  '#3949ab',
  '#d81b60',
  '#039be5',
  '#6d4c41',
]

function colorOf(name: string): string {
  let hash = 0
  for (const char of name) hash = (Math.imul(hash, 31) + char.charCodeAt(0)) | 0
  return COLORS[Math.abs(hash) % COLORS.length]
}

interface AvatarProps {
  name: string
  src?: string | null
  size: number
}

/** Decorative: the name is always shown next to it. */
export default function Avatar({ name, src, size }: AvatarProps) {
  if (src) {
    return <img className={styles.avatar} src={src} alt="" width={size} height={size} />
  }
  const letter = Array.from(name.trim())[0]?.toUpperCase() ?? '?'
  return (
    <span
      className={styles.avatar}
      style={{ width: size, height: size, background: colorOf(name), fontSize: size * 0.55 }}
      aria-hidden="true"
    >
      {letter}
    </span>
  )
}
