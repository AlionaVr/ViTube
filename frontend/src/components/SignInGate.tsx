import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { useViewer } from '../viewer/useViewer'
import Popover, { type TriggerProps } from './Popover'
import styles from './SignInGate.module.css'

interface SignInGateProps {
  /** YouTube's wording, e.g. "Like this video?" */
  title: string
  text: string
  onAction: () => void
  align?: 'start' | 'end'
  children: (props: TriggerProps) => ReactNode
}

/**
 * Renders the button. A signed-in viewer gets the action; a guest gets YouTube's
 * "Sign in to …" card instead. Disabled while we don't know yet.
 */
export default function SignInGate({ title, text, onAction, align, children }: SignInGateProps) {
  const viewer = useViewer()
  if (viewer.status !== 'guest') {
    return children({ onClick: onAction, disabled: viewer.status === 'loading' })
  }
  return (
    <Popover label={title} align={align} trigger={children}>
      {() => (
        <div className={styles.card}>
          <p className={styles.title}>{title}</p>
          <p className={styles.text}>{text}</p>
          <Link to="/login" className={styles.signIn}>
            Sign in
          </Link>
        </div>
      )}
    </Popover>
  )
}
