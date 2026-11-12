import { VISIBILITY } from '../playlists/visibility'
import type { Visibility } from '../videos/types'
import Icon from './Icon'
import styles from './VisibilityBadge.module.css'

/** YouTube's gray badge under a card's details: only for what isn't public. */
export default function VisibilityBadge({ visibility }: { visibility: Visibility }) {
  if (visibility === 'public') return null
  const { label, icon } = VISIBILITY[visibility]
  return (
    <p className={styles.badge}>
      <Icon name={icon} size={14} />
      {label}
    </p>
  )
}
