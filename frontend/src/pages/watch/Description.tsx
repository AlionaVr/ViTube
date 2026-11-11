import { useState } from 'react'

import { formatCompact, formatDate, formatExact, formatTimeAgo } from '../../lib/format'
import type { Video } from '../../videos/types'
import styles from './Description.module.css'

/** YouTube's grey box: two lines and "...more"; the whole box expands on click. */
export default function Description({ video }: { video: Video }) {
  const [expanded, setExpanded] = useState(false)

  if (!expanded) {
    return (
      // The button below is the keyboard way in; a click anywhere on the box is a shortcut.
      <div className={`${styles.box} ${styles.collapsed}`} onClick={() => setExpanded(true)}>
        <p className={styles.info}>
          <span>{formatCompact(video.view_count)} views</span>
          <span>{formatTimeAgo(video.created_at)}</span>
        </p>
        <p className={styles.text}>{video.description}</p>
        <button
          type="button"
          className={styles.more}
          aria-expanded={false}
          onClick={(event) => {
            event.stopPropagation()
            setExpanded(true)
          }}
        >
          ...more
        </button>
      </div>
    )
  }

  return (
    <div className={styles.box}>
      <p className={styles.info}>
        <span>{formatExact(video.view_count)} views</span>
        <span>{formatDate(video.created_at)}</span>
      </p>
      <p className={styles.fullText}>{video.description}</p>
      <button
        type="button"
        className={styles.less}
        aria-expanded={true}
        onClick={() => setExpanded(false)}
      >
        Show less
      </button>
    </div>
  )
}
