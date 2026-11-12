import IconButton from '../components/IconButton'
import { watchUrl } from '../videos/paths'
import styles from './UploadDialog.module.css'

/** The details form's link to the video, with Studio's copy button. */
export default function VideoLink({ id, onCopied }: { id: string; onCopied: () => void }) {
  const link = `${window.location.origin}${watchUrl(id)}`
  // No clipboard API on plain-HTTP sites other than localhost: no button then.
  const canCopy = typeof navigator.clipboard?.writeText === 'function'

  async function copy() {
    await navigator.clipboard.writeText(link)
    onCopied()
  }

  return (
    <dd className={styles.linkRow}>
      <a href={link} target="_blank" rel="noreferrer">
        {link}
      </a>
      {canCopy && <IconButton icon="copy" label="Copy video link" onClick={() => void copy()} />}
    </dd>
  )
}
