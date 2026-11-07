import { useEffect, useRef, useState } from 'react'

import IconButton from './IconButton'
import styles from './ChipBar.module.css'

export interface Chip {
  id: string | null
  label: string
}

interface ChipBarProps {
  chips: Chip[]
  selected: string | null
  onSelect: (id: string | null) => void
  label: string
}

/** A row of filter chips; arrows appear when it overflows, as on YouTube. */
export default function ChipBar({ chips, selected, onSelect, label }: ChipBarProps) {
  const row = useRef<HTMLDivElement>(null)
  const [canScroll, setCanScroll] = useState({ left: false, right: false })

  useEffect(() => {
    const element = row.current
    if (!element) return
    const update = () =>
      setCanScroll({
        left: element.scrollLeft > 0,
        right: element.scrollLeft + element.clientWidth < element.scrollWidth - 1,
      })
    // Fires once right away, then on every resize (the guide opening changes the width).
    const observer = new ResizeObserver(update)
    observer.observe(element)
    element.addEventListener('scroll', update, { passive: true })
    return () => {
      observer.disconnect()
      element.removeEventListener('scroll', update)
    }
  }, [chips.length])

  const scrollBy = (direction: -1 | 1) =>
    row.current?.scrollBy({
      left: direction * row.current.clientWidth * 0.8,
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
    })

  return (
    <div className={styles.bar}>
      {canScroll.left && (
        <div className={`${styles.arrow} ${styles.left}`}>
          <IconButton icon="chevronLeft" label="Previous" onClick={() => scrollBy(-1)} />
        </div>
      )}
      <div ref={row} className={styles.row} role="group" aria-label={label}>
        {chips.map((chip) => (
          <button
            key={chip.id ?? 'all'}
            type="button"
            className={styles.chip}
            aria-pressed={chip.id === selected}
            onClick={() => onSelect(chip.id)}
          >
            {chip.label}
          </button>
        ))}
      </div>
      {canScroll.right && (
        <div className={`${styles.arrow} ${styles.right}`}>
          <IconButton icon="chevronRight" label="Next" onClick={() => scrollBy(1)} />
        </div>
      )}
    </div>
  )
}
