import type { CSSProperties } from 'react'

import styles from './Fireworks.module.css'

// The brand red with three festive colors.
const COLORS = ['var(--color-brand)', '#ffb000', '#3ea6ff', '#2ba640']
const OUTER = 12
const INNER = 8

// Two rings: a wide one, then a short one turned half a step, a moment later.
const SPARKS = [
  ...Array.from({ length: OUTER }, (_, i) => ({
    angle: (360 / OUTER) * i,
    distance: 36,
    delay: 0,
  })),
  ...Array.from({ length: INNER }, (_, i) => ({
    angle: (360 / INNER) * (i + 0.5),
    distance: 24,
    delay: 120,
  })),
]

/** A burst of sparks from the middle of its parent. Decorative: aria-pressed says what happened. */
export default function Fireworks({ onDone }: { onDone: () => void }) {
  return (
    <span
      className={styles.burst}
      aria-hidden="true"
      data-fireworks=""
      // The sparks' own animation ends bubble up too; the burst's own end means all are done.
      onAnimationEnd={(event) => event.target === event.currentTarget && onDone()}
    >
      {SPARKS.map((spark, i) => (
        <i
          key={i}
          className={styles.spark}
          style={
            {
              '--angle': `${spark.angle}deg`,
              '--distance': `${spark.distance}px`,
              '--delay': `${spark.delay}ms`,
              '--color': COLORS[i % COLORS.length],
            } as CSSProperties
          }
        />
      ))}
    </span>
  )
}
