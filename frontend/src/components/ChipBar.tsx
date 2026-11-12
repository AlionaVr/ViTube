import { useScrollArrows } from '../hooks/useScrollArrows'
import IconButton from './IconButton'
import styles from './ChipBar.module.css'

/** `id: null` is the "All" chip. */
export interface Chip<T extends string> {
  id: T | null
  label: string
}

interface ChipBarProps<T extends string> {
  chips: Chip<T>[]
  selected: T | null
  onSelect: (id: T | null) => void
  label: string
}

/** A row of filter chips; arrows appear when it overflows, as on YouTube. */
export default function ChipBar<T extends string>({
  chips,
  selected,
  onSelect,
  label,
}: ChipBarProps<T>) {
  const { row, canScroll, scrollBy } = useScrollArrows<HTMLDivElement>(chips.length)

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
