import styles from './Logo.module.css'

// Own logo: a play circle and a wordmark. Not YouTube's brand assets.
export default function Logo() {
    return (
        <span className={styles.logo}>
      <svg viewBox="0 0 24 24" width="28" height="28" aria-hidden="true">
        <circle cx="12" cy="12" r="12" fill="var(--color-brand)"/>
        <path d="M9.5 7.5v9l7-4.5z" fill="#fff"/>
      </svg>
      <span className={styles.wordmark}>ViTube</span>
    </span>
    )
}
