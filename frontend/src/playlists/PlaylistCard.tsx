import { Link } from 'react-router'

import Icon from '../components/Icon'
import { formatVideoCount } from '../lib/format'
import styles from './PlaylistCard.module.css'
import type { Playlist } from './types'

/** YouTube's playlist card: a cover on a stack, the count on it, the title, `lines` of detail. */
export default function PlaylistCard({
  playlist,
  url,
  lines = [],
}: {
  /** A stored playlist, or Liked videos. */
  playlist: Pick<Playlist, 'title' | 'thumbnail_url' | 'video_count'>
  url: string
  lines?: string[]
}) {
  return (
    <article className={styles.card}>
      {/* The title link names the playlist; this one is a larger target for the same page. */}
      <Link to={url} className={styles.cover} tabIndex={-1} aria-hidden="true">
        <div className={styles.image}>
          {playlist.thumbnail_url ? (
            <img src={playlist.thumbnail_url} alt="" loading="lazy" decoding="async" />
          ) : (
            <Icon name="playlists" size={36} />
          )}
        </div>
        <span className={styles.badge}>
          <Icon name="playlists" size={16} />
          {formatVideoCount(playlist.video_count)}
        </span>
      </Link>
      <h3 className={styles.title}>
        <Link to={url} title={playlist.title}>
          {playlist.title}
        </Link>
      </h3>
      {lines.map((line) => (
        <p key={line} className={styles.line}>
          {line}
        </p>
      ))}
      <Link to={url} className={styles.full}>
        View full playlist
      </Link>
    </article>
  )
}

export function PlaylistCardSkeleton() {
  return (
    <div className={styles.card}>
      <div className={`${styles.image} ${styles.ghost}`} />
      <div className={styles.ghostLine} />
      <div className={`${styles.ghostLine} ${styles.ghostShort}`} />
    </div>
  )
}
