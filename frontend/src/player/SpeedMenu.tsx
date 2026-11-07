import { useEffect, useRef, useState } from 'react'

import Icon from '../components/Icon'
import ControlButton from './ControlButton'
import styles from './Player.module.css'
import { SPEEDS } from './settings'

const speedLabel = (rate: number) => (rate === 1 ? 'Normal' : String(rate))

interface SpeedMenuProps {
  rate: number
  open: boolean
  onOpenChange: (open: boolean) => void
  onChange: (rate: number) => void
}

/** The settings panel: "Playback speed › Normal", then the list of speeds. */
export default function SpeedMenu({ rate, open, onOpenChange, onChange }: SpeedMenuProps) {
  const root = useRef<HTMLDivElement>(null)
  const [page, setPage] = useState<'main' | 'speed'>('main')

  useEffect(() => {
    if (!open) return
    const onPointerDown = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) onOpenChange(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [open, onOpenChange])

  function toggle() {
    setPage('main')
    onOpenChange(!open)
  }

  return (
    <div
      ref={root}
      className={styles.settings}
      onKeyDown={(event) => {
        if (event.key === 'Escape' && open) {
          event.stopPropagation()
          onOpenChange(false)
        }
      }}
    >
      {open && (
        <div className={styles.menu} role="menu" aria-label="Settings">
          {page === 'main' ? (
            <button
              type="button"
              role="menuitem"
              className={styles.menuItem}
              onClick={() => setPage('speed')}
            >
              <span className={styles.menuLabel}>Playback speed</span>
              <span className={styles.menuValue}>{speedLabel(rate)}</span>
              <Icon name="chevronRight" />
            </button>
          ) : (
            <>
              <button
                type="button"
                className={`${styles.menuItem} ${styles.menuHeader}`}
                onClick={() => setPage('main')}
              >
                <Icon name="chevronLeft" />
                Playback speed
              </button>
              {SPEEDS.map((speed) => (
                <button
                  key={speed}
                  type="button"
                  role="menuitemradio"
                  aria-checked={speed === rate}
                  className={styles.menuItem}
                  onClick={() => {
                    onChange(speed)
                    onOpenChange(false)
                  }}
                >
                  <span className={styles.menuCheck}>
                    {speed === rate && <Icon name="check" />}
                  </span>
                  {speedLabel(speed)}
                </button>
              ))}
            </>
          )}
        </div>
      )}
      <ControlButton
        icon="settings"
        label="Settings"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={toggle}
      />
    </div>
  )
}
