import styles from './ErrorState.module.css'

interface ErrorStateProps {
  title: string
  onRetry: () => void
}

/** A failed load: what happened and one way out. */
export default function ErrorState({ title, onRetry }: ErrorStateProps) {
  return (
    <div className={styles.root} role="alert">
      <p className={styles.title}>{title}</p>
      <p className={styles.hint}>Check your connection and try again.</p>
      <button type="button" className={styles.retry} onClick={onRetry}>
        Retry
      </button>
    </div>
  )
}
