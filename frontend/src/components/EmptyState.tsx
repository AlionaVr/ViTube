import type { ReactNode } from 'react'

import styles from './EmptyState.module.css'

export default function EmptyState({
  title,
  children,
  action,
}: {
  title: string
  children?: ReactNode
  /** A button that fills the emptiness, under the text. */
  action?: ReactNode
}) {
  return (
    <div className={styles.root}>
      <h1>{title}</h1>
      {children && <p>{children}</p>}
      {action && <div className={styles.action}>{action}</div>}
    </div>
  )
}
