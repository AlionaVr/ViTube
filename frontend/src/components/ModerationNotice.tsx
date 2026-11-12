import type { ReactNode } from 'react'

import Icon from './Icon'
import styles from './ModerationNotice.module.css'

interface ModerationNoticeProps {
  title: string
  children: ReactNode
  className?: string
}

/** Tells the owner or a moderator, who still see restricted content, that others don't (ADR 0009). */
export default function ModerationNotice({ title, children, className }: ModerationNoticeProps) {
  return (
    <div className={className ? `${styles.notice} ${className}` : styles.notice} role="note">
      <Icon name="shieldPerson" />
      <div>
        <p className={styles.title}>{title}</p>
        <p className={styles.text}>{children}</p>
      </div>
    </div>
  )
}
