import { type ReactNode, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'

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

const GAP = 8 // between the button and the card, and the card and the window's edge

/** Where the card goes: under its button, or over it when the window has no room below. */
function place(panel: HTMLElement, button: HTMLElement, align: 'start' | 'end') {
  const box = button.getBoundingClientRect()
  const { offsetWidth: width, offsetHeight: height } = panel
  const below = box.bottom + GAP
  const fits = below + height <= window.innerHeight || box.top - GAP - height < 0
  const left = align === 'end' ? box.right - width : box.left
  const maxLeft = document.documentElement.clientWidth - width - GAP
  panel.style.top = `${fits ? below : box.top - GAP - height}px`
  panel.style.left = `${Math.max(GAP, Math.min(left, maxLeft))}px`
}

/** A small card under its button. Closes on a click outside or Escape; focus moves in and back.
 * The card opens in the top layer: no scrolling box (a table, a dialog) can clip it. */
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

  // Before paint: the card shows where it belongs, and follows its button while anything scrolls.
  useLayoutEffect(() => {
    const card = panel.current
    const button = root.current
    if (!open || !card || !button) return
    card.showPopover?.() // no Popover API (old browsers): fixed in the page, still unclipped
    const follow = () => place(card, button, align)
    follow()
    window.addEventListener('scroll', follow, true)
    window.addEventListener('resize', follow)
    return () => {
      window.removeEventListener('scroll', follow, true)
      window.removeEventListener('resize', follow)
    }
  }, [open, align])

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
          popover="manual"
          className={styles.panel}
          role={role}
          aria-label={label}
        >
          {children(close)}
        </div>
      )}
    </div>
  )
}
