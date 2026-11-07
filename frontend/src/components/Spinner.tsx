import styles from './Spinner.module.css'

/** YouTube's loading circle. */
export default function Spinner({
  label = 'Loading',
  size = 32,
}: {
  label?: string
  size?: number
}) {
  return (
    <span
      className={styles.spinner}
      role="status"
      aria-label={label}
      style={{ width: size, height: size }}
    />
  )
}
