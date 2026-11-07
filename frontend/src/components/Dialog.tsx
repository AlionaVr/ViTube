import { type ReactNode, useRef } from 'react'

import { useModalDialog } from '../hooks/useModalDialog'
import styles from './Dialog.module.css'

interface DialogProps {
  open: boolean
  onClose: () => void
  label: string
  children: ReactNode
}

/** A centered modal card. The browser traps focus and closes it on Escape; a click outside closes it too. */
export default function Dialog({ open, onClose, label, children }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null)
  useModalDialog(ref, open)

  return (
    <dialog
      ref={ref}
      className={styles.dialog}
      aria-label={label}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div className={styles.content}>{children}</div>
    </dialog>
  )
}
