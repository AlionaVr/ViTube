import { useEffect, useRef, useState } from 'react'

import styles from './ClampedText.module.css'

/** Text cut to `lines` with "Read more"; the button shows only when something is cut. */
export default function ClampedText({ text, lines }: { text: string; lines: number }) {
  const ref = useRef<HTMLParagraphElement>(null)
  const [expanded, setExpanded] = useState(false)
  const [overflows, setOverflows] = useState(false)

  useEffect(() => {
    const element = ref.current
    if (!element || expanded) return
    const observer = new ResizeObserver(() =>
      setOverflows(element.scrollHeight > element.clientHeight + 1),
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [expanded, text])

  return (
    <>
      <p
        ref={ref}
        className={expanded ? styles.text : `${styles.text} ${styles.clamped}`}
        style={{ WebkitLineClamp: lines, lineClamp: lines }}
      >
        {text}
      </p>
      {(overflows || expanded) && (
        <button
          type="button"
          className={styles.toggle}
          aria-expanded={expanded}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? 'Show less' : 'Read more'}
        </button>
      )}
    </>
  )
}
