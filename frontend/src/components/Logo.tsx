import styles from './Logo.module.css'

interface LogoProps {
  size?: number
  wordmark?: boolean
}

// Own logo: a play circle and a wordmark. Not YouTube's brand assets.
export default function Logo({ size = 28, wordmark = true }: LogoProps) {
  return (
    <span className={styles.logo}>
      <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true">
        <circle cx="12" cy="12" r="12" fill="var(--color-brand)" />
        <path d="M9.5 7.5v9l7-4.5z" fill="#fff" />
      </svg>
      {wordmark && <span className={styles.wordmark}>ViTube</span>}
    </span>
  )
}
