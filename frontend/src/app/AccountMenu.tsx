import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router'

import type { User } from '../api/client'
import { useSignOut } from '../auth/hooks'
import Avatar from '../components/Avatar'
import Icon from '../components/Icon'
import { canModerate } from '../moderation/roles'
import { channelUrl } from '../videos/paths'
import styles from './AccountMenu.module.css'
import menu from './headerMenu.module.css'
import MenuPages from './MenuPages'

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
        <Avatar name={user.email} size={32} />
      </button>

      {open && (
        <div id={panelId} className={styles.panel}>
          <MenuPages>
            <div className={styles.account}>
              <Avatar name={user.email} size={40} />
              <div className={styles.names}>
                <p className={styles.name}>{user.email}</p>
                <p className={styles.handle}>@{user.handle}</p>
                <Link
                  to={channelUrl(user.handle)}
                  className={styles.channelLink}
                  onClick={() => setOpen(false)}
                >
                  View your channel
                </Link>
              </div>
            </div>
            <hr className={menu.divider} />
            <button
              type="button"
              className={menu.item}
              onClick={() => {
                setOpen(false)
                signOut.mutate()
              }}
            >
              <Icon name="signOut" />
              Sign out
            </button>
            {/* A staff tool gets its own group after Sign out, as YouTube Studio does. */}
            {canModerate(user) && (
              <>
                <hr className={menu.divider} />
                <Link to="/moderation" className={menu.item} onClick={() => setOpen(false)}>
                  <Icon name="shieldPerson" />
                  Moderation
                </Link>
              </>
            )}
          </MenuPages>
        </div>
      )}
    </div>
  )
}
