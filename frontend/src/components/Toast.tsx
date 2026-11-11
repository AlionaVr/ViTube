import { type ReactNode, useCallback, useEffect, useRef, useState } from 'react'

import { ToastContext } from '../hooks/useToast'
import styles from './Toast.module.css'

const SHOWN_MS = 4000

interface Shown {
  id: number
  message: string
}

/** YouTube's toast: one short line at the bottom left that confirms what an action did. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [shown, setShown] = useState<Shown | null>(null)
  const show = useCallback(
    (message: string) => setShown((last) => ({ id: (last?.id ?? 0) + 1, message })),
    [],
  )

  useEffect(() => {
    if (!shown) return
    const timer = setTimeout(() => setShown(null), SHOWN_MS)
    return () => clearTimeout(timer)
  }, [shown])

  return (
    <ToastContext value={show}>
      {children}
      <Toast shown={shown} />
    </ToastContext>
  )
}

function Toast({ shown }: { shown: Shown | null }) {
  const ref = useRef<HTMLDivElement>(null)

  // A popover sits in the top layer: over a modal dialog too, as long as it opens after it.
  useEffect(() => {
    const element = ref.current
    if (!element?.showPopover) return // no Popover API (old browsers, jsdom): stays in the page
    if (element.matches(':popover-open')) element.hidePopover()
    if (shown) element.showPopover()
  }, [shown])

  return (
    <div ref={ref} popover="manual" role="status" className={styles.toast}>
      {/* A new key restarts the entrance for each toast. */}
      {shown && (
        <p key={shown.id} className={styles.message}>
          {shown.message}
        </p>
      )}
    </div>
  )
}
