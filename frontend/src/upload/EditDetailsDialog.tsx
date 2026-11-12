import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useId, useRef, useState } from 'react'

import IconButton from '../components/IconButton'
import { useModalDialog } from '../hooks/useModalDialog'
import { useToast } from '../hooks/useToast'
import buttons from '../styles/buttons.module.css'
import { videoKeys } from '../videos/hooks'
import type { OwnVideo } from '../videos/types'
import { updateVideo } from './api'
import { changedDetails, detailsOf } from './details'
import DetailsFields from './DetailsFields'
import styles from './UploadDialog.module.css'
import VideoLink from './VideoLink'
import VideoScreen from './VideoScreen'

const NOT_READY: Record<Exclude<OwnVideo['status'], 'ready'>, string> = {
  uploading: 'Draft',
  uploaded: 'Processing video…',
  processing: 'Processing video…',
  failed: 'Processing failed',
}

/** Studio's video details for a video that exists: the upload dialog's form. Mounted while open. */
export default function EditDetailsDialog({
  video,
  onClose,
}: {
  video: OwnVideo
  onClose: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const headingId = useId()
  useModalDialog(ref, true)
  const [details, setDetails] = useState(() => detailsOf(video))
  const changes = changedDetails(detailsOf(video), details)
  const queryClient = useQueryClient()
  const toast = useToast()
  const save = useMutation({
    mutationFn: () => updateVideo(video.id, changes),
    onSuccess: () => {
      // Its lists, its page and the owner's channel: a new title or visibility shows everywhere.
      void queryClient.invalidateQueries({ queryKey: videoKeys.all })
      toast('Changes saved')
      onClose()
    },
  })
  const [copied, setCopied] = useState(false)
  const changed = Object.keys(changes).length > 0

  // As in Studio: unsaved changes are not dropped without asking.
  function requestClose() {
    if (changed && !window.confirm('Discard unsaved changes?')) return
    onClose()
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    save.mutate()
  }

  return (
    <dialog
      ref={ref}
      className={styles.dialog}
      aria-labelledby={headingId}
      onCancel={(event) => {
        event.preventDefault() // Escape: ask first if there are changes
        requestClose()
      }}
    >
      <div className={styles.header}>
        <h2 id={headingId} className={styles.heading}>
          Video details
        </h2>
        <IconButton icon="close" label="Close" onClick={requestClose} />
      </div>
      <form className={styles.details} onSubmit={submit}>
        <div className={styles.body}>
          <div className={styles.fields}>
            <DetailsFields details={details} onChange={setDetails} />
          </div>
          <aside className={styles.side}>
            <VideoScreen video={video}>
              {video.status !== 'ready' && <span>{NOT_READY[video.status]}</span>}
            </VideoScreen>
            <dl className={styles.facts}>
              <dt>Video link</dt>
              <VideoLink id={video.id} onCopied={() => setCopied(true)} />
            </dl>
          </aside>
        </div>
        <div className={styles.footer}>
          <span className={styles.status}>
            <span role="status">{copied && !save.isError && 'Link copied'}</span>
            <span className={styles.errorText} role="alert">
              {save.isError && save.error.message}
            </span>
          </span>
          <button
            type="button"
            className={`${buttons.pill} ${buttons.text}`}
            onClick={requestClose}
          >
            Cancel
          </button>
          {/* As in Studio: nothing to save until something changes. */}
          <button
            type="submit"
            className={`${buttons.pill} ${buttons.primary}`}
            disabled={!changed || !details.title.trim() || save.isPending}
          >
            Save
          </button>
        </div>
      </form>
    </dialog>
  )
}
