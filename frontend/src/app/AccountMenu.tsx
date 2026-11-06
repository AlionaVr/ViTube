import { useEffect, useId, useRef, useState } from 'react'

import type { User } from '../api/client'
import { useSignOut } from '../auth/hooks'
import Avatar from '../components/Avatar'
import Icon from '../components/Icon'
import styles from './AccountMenu.module.css'

/** The avatar in the header and the panel it opens (a disclosure: Tab moves through it). */
export default function AccountMenu({ user }: { user: User }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const panelId = useId()
  const signOut = useSignOut()

  // Open: a click outside or Escape closes it. Escape also returns focus to the avatar.
  useEffect(() => {
    if (!open) return
    function onPointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== 'Escape') return
      setOpen(false)
      buttonRef.current?.focus()
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  return (
    <div className={styles.root} ref={rootRef}>
      <button
        ref={buttonRef}
        type="button"
        className={styles.avatarButton}
        aria-label="Account menu"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((isOpen) => !isOpen)}
      >
        <Avatar user={user} size={32} />
      </button>

      {open && (
        <div id={panelId} className={styles.panel}>
          <div className={styles.account}>
            <Avatar user={user} size={40} />
            <div className={styles.names}>
              <p className={styles.name}>{user.email}</p>
              <p className={styles.handle}>@{user.handle}</p>
            </div>
          </div>
          <hr className={styles.divider} />
          <button
            type="button"
            className={styles.item}
            onClick={() => {
              setOpen(false)
              signOut.mutate()
            }}
          >
            <Icon name="signOut" />
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}
