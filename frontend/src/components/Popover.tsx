import { type ReactNode, useEffect, useId, useRef, useState } from 'react'

import styles from './Popover.module.css'

export interface TriggerProps {
  onClick: () => void
  disabled?: boolean
  'aria-expanded'?: boolean
  'aria-haspopup'?: 'dialog' | 'menu'
  'aria-controls'?: string
}

interface PopoverProps {
  label: string
  role?: 'dialog' | 'menu'
  align?: 'start' | 'end'
  trigger: (props: TriggerProps) => ReactNode
  children: (close: () => void) => ReactNode
}

/** A small card under its button. Closes on a click outside or Escape; focus moves in and back. */
export default function Popover({
  label,
  role = 'dialog',
  align = 'start',
  trigger,
  children,
}: PopoverProps) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  const wasOpen = useRef(false)
  const id = useId()

  useEffect(() => {
    if (!open) {
      // The panel took the focus with it: give it back to the button (Escape, a menu choice).
      if (wasOpen.current && document.activeElement === document.body) {
        root.current?.querySelector<HTMLElement>('[aria-haspopup]')?.focus()
      }
      wasOpen.current = false
      return
    }
    wasOpen.current = true
    panel.current?.querySelector<HTMLElement>('a, button')?.focus()
    const onPointerDown = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [open])

  const close = () => setOpen(false)

  return (
    <div
      ref={root}
      className={styles.root}
      onKeyDown={(event) => {
        if (event.key === 'Escape' && open) {
          event.stopPropagation()
          close()
        }
      }}
    >
      {trigger({
        onClick: () => setOpen((value) => !value),
        'aria-expanded': open,
        'aria-haspopup': role,
        'aria-controls': open ? id : undefined,
      })}
      {open && (
        <div
          ref={panel}
          id={id}
          className={align === 'end' ? `${styles.panel} ${styles.end}` : styles.panel}
          role={role}
          aria-label={label}
        >
          {children(close)}
        </div>
      )}
    </div>
  )
}
