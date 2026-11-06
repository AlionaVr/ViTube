import { useEffect, useRef } from 'react'
import { Link } from 'react-router'

import IconButton from '../components/IconButton'
import Logo from '../components/Logo'
import styles from './GuideDrawer.module.css'
import { GuideContent } from './Sidebar'

interface GuideDrawerProps {
  open: boolean
  onClose: () => void
}

/**
 * The guide over the page, with a scrim (narrow screens and the watch page).
 * A modal <dialog>: the browser traps focus, closes it on Escape and makes the page inert.
 */
export default function GuideDrawer({ open, onClose }: GuideDrawerProps) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    // The scrim is the dialog's ::backdrop; a click there targets the dialog itself.
    <dialog
      ref={ref}
      id="guide"
      className={styles.drawer}
      aria-label="Guide"
      onClose={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div className={styles.panel}>
        <div className={styles.header}>
          <IconButton icon="menu" label="Menu" onClick={onClose} />
          <Link to="/" className={styles.logo} aria-label="ViTube home" onClick={onClose}>
            <Logo />
          </Link>
        </div>
        <nav className={styles.content} aria-label="Main">
          <GuideContent onNavigate={onClose} />
        </nav>
      </div>
    </dialog>
  )
}
