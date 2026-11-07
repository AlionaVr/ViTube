import { useRef, useState } from 'react'

import Dialog from '../../components/Dialog'
import IconButton from '../../components/IconButton'
import buttons from '../../styles/buttons.module.css'
import { watchUrl } from '../../videos/paths'
import styles from './ShareDialog.module.css'

interface ShareDialogProps {
  videoId: string
  open: boolean
  onClose: () => void
}

export default function ShareDialog({ videoId, open, onClose }: ShareDialogProps) {
  const input = useRef<HTMLInputElement>(null)
  const [copied, setCopied] = useState(false)
  const url = `${window.location.origin}${watchUrl(videoId)}`

  async function copy() {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
    } catch {
      // No clipboard access (e.g. plain http): select the link so Ctrl+C works.
      input.current?.select()
    }
  }

  function close() {
    setCopied(false)
    onClose()
  }

  return (
    <Dialog open={open} onClose={close} label="Share">
      <div className={styles.header}>
        <h2 className={styles.title}>Share</h2>
        <IconButton icon="close" label="Close" onClick={close} />
      </div>
      <div className={styles.link}>
        <input
          ref={input}
          className={styles.url}
          value={url}
          readOnly
          aria-label="Video link"
          onFocus={(event) => event.target.select()}
        />
        <button type="button" className={`${buttons.pill} ${buttons.primary}`} onClick={copy}>
          Copy
        </button>
      </div>
      <p className={styles.status} role="status">
        {copied && 'Link copied to clipboard'}
      </p>
    </Dialog>
  )
}
