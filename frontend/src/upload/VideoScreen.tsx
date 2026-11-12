import type { ReactNode } from 'react'

import type { OwnVideo } from '../videos/types'
import styles from './UploadDialog.module.css'

/** The details form's preview: the player once the video is ready, else what is going on. */
export default function VideoScreen({ video, children }: { video: OwnVideo; children: ReactNode }) {
  if (video.status === 'ready' && video.media_url) {
    return (
      <video
        className={styles.screen}
        src={video.media_url}
        poster={video.thumbnail_url ?? undefined}
        controls
        preload="metadata"
        aria-label="Video preview"
      />
    )
  }
  return <div className={`${styles.screen} ${styles.placeholder}`}>{children}</div>
}
