import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useId, useRef, useState } from 'react'

import Icon from '../components/Icon'
import IconButton from '../components/IconButton'
import Spinner from '../components/Spinner'
import { useModalDialog } from '../hooks/useModalDialog'
import buttons from '../styles/buttons.module.css'
import { videoKeys } from '../videos/hooks'
import { watchUrl } from '../videos/paths'
import type { OwnVideo } from '../videos/types'
import { updateVideo } from './api'
import { detailsOf } from './details'
import DetailsFields from './DetailsFields'
import { formatLimits } from './format'
import styles from './UploadDialog.module.css'
import { type Transfer, useUpload } from './useUpload'
import VideoScreen from './VideoScreen'

/** YouTube Studio's "Upload videos" modal. Mounted while open; closing unmounts it. */
export default function UploadDialog({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  const headingId = useId()
  const upload = useUpload()
  useModalDialog(ref, true)

  function requestClose() {
    if (upload.busy && !window.confirm('Your upload will stop. Close anyway?')) return
    upload.cancel()
    onClose()
  }

  return (
    <dialog
      ref={ref}
      className={styles.dialog}
      aria-labelledby={headingId}
      onCancel={(event) => {
        event.preventDefault() // Escape: ask first if the upload would stop
        requestClose()
      }}
    >
      <div className={styles.header}>
        <h2 id={headingId} className={styles.heading}>
          {upload.video?.title ?? 'Upload videos'}
        </h2>
        <IconButton icon="close" label="Close" onClick={requestClose} />
      </div>
      {upload.video && upload.file ? (
        <Details
          key={upload.video.id}
          video={upload.video}
          fileName={upload.file.name}
          transfer={upload.transfer}
          onRetry={upload.retry}
        />
      ) : (
        <FilePicker
          limits={upload.limits ? formatLimits(upload.limits) : null}
          error={upload.pickError}
          onFile={upload.pick}
        />
      )}
    </dialog>
  )
}

function FilePicker({
  limits,
  error,
  onFile,
}: {
  limits: string | null
  error: string | null
  onFile: (file: File) => void
}) {
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const choose = () => input.current?.click()

  return (
    <div
      className={dragging ? `${styles.picker} ${styles.dragging}` : styles.picker}
      onDragOver={(event) => {
        event.preventDefault() // allows the drop
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault()
        setDragging(false)
        const file = event.dataTransfer.files[0]
        if (file) onFile(file)
      }}
    >
      {/* Mouse shortcut, as on YouTube; keyboard users have the button below. */}
      <div className={styles.circle} aria-hidden="true" onClick={choose}>
        <Icon name="upload" size={64} />
      </div>
      <p className={styles.pickerTitle}>Drag and drop a video file to upload</p>
      <p className={styles.pickerHint}>Your video will be private until you publish it.</p>
      {error && (
        <p className={styles.error} role="alert">
          <Icon name="errorFill" size={16} />
          {error}
        </p>
      )}
      <button type="button" className={`${buttons.pill} ${buttons.primary}`} onClick={choose}>
        Select file
      </button>
      <input
        ref={input}
        type="file"
        accept="video/*"
        hidden
        data-testid="file-input"
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = '' // the same file can be picked again
          if (file) onFile(file)
        }}
      />
      {limits && <p className={styles.limits}>{limits}</p>}
    </div>
  )
}

function Details({
  video,
  fileName,
  transfer,
  onRetry,
}: {
  video: OwnVideo
  fileName: string
  transfer: Transfer
  onRetry: () => void
}) {
  const [details, setDetails] = useState(() => detailsOf(video))
  const queryClient = useQueryClient()
  const save = useMutation({
    mutationFn: () => updateVideo(video.id, details),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: videoKeys.mine }),
  })
  const link = `${window.location.origin}${watchUrl(video.id)}`
  const [copied, setCopied] = useState(false)
  // No clipboard API on plain-HTTP sites other than localhost: no button then.
  const canCopy = typeof navigator.clipboard?.writeText === 'function'

  async function copyLink() {
    await navigator.clipboard.writeText(link)
    setCopied(true)
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    save.mutate()
  }

  return (
    <form className={styles.details} onSubmit={submit}>
      <div className={styles.body}>
        <div className={styles.fields}>
          <DetailsFields details={details} onChange={setDetails} />
        </div>
        <aside className={styles.side}>
          <Preview video={video} transfer={transfer} />
          <dl className={styles.facts}>
            <dt>Video link</dt>
            <dd className={styles.linkRow}>
              <a href={link} target="_blank" rel="noreferrer">
                {link}
              </a>
              {canCopy && <IconButton icon="copy" label="Copy video link" onClick={copyLink} />}
            </dd>
            <dt>Filename</dt>
            <dd>{fileName}</dd>
          </dl>
        </aside>
      </div>
      <div className={styles.footer}>
        <Status video={video} transfer={transfer} onRetry={onRetry} />
        <span className={styles.saved} role="status">
          {copied && !save.isSuccess && 'Link copied'}
          {save.isSuccess && 'Details saved'}
          {save.isError && <span className={styles.errorText}>{save.error.message}</span>}
        </span>
        <button
          type="submit"
          className={`${buttons.pill} ${buttons.primary}`}
          disabled={!details.title.trim() || save.isPending}
        >
          Save
        </button>
      </div>
    </form>
  )
}

function Preview({ video, transfer }: { video: OwnVideo; transfer: Transfer }) {
  const text =
    video.status === 'failed'
      ? 'Processing failed'
      : transfer.phase === 'stored'
        ? 'Processing video…'
        : 'Uploading video…'
  return (
    <VideoScreen video={video}>
      {transfer.phase === 'stored' && video.status !== 'failed' && (
        <Spinner label="Processing" size={28} />
      )}
      <span>{text}</span>
    </VideoScreen>
  )
}

function Status({
  video,
  transfer,
  onRetry,
}: {
  video: OwnVideo
  transfer: Transfer
  onRetry: () => void
}) {
  if (transfer.phase === 'sending') {
    const percent = Math.floor(transfer.progress * 100)
    return (
      <div className={styles.status}>
        <Icon name="upload" size={20} />
        <span>Uploading {percent}%</span>
        <progress className={styles.progress} value={percent} max={100} aria-label="Upload" />
      </div>
    )
  }
  if (transfer.phase === 'failed') {
    return (
      <div className={`${styles.status} ${styles.errorText}`} role="alert">
        <Icon name="errorFill" size={20} />
        <span>{transfer.message}</span>
        <button type="button" className={`${buttons.pill} ${buttons.link}`} onClick={onRetry}>
          Try again
        </button>
      </div>
    )
  }
  if (video.status === 'failed') {
    return (
      <div className={`${styles.status} ${styles.errorText}`} role="alert">
        <Icon name="errorFill" size={20} />
        <span>Processing failed. {video.error_message}</span>
      </div>
    )
  }
  if (video.status === 'ready') {
    return (
      <div className={styles.status} role="status">
        <Icon name="check" size={20} />
        <span>Processing complete</span>
      </div>
    )
  }
  return (
    <div className={styles.status} role="status">
      {transfer.phase === 'stored' ? 'Upload complete. Processing…' : 'Getting ready to upload…'}
    </div>
  )
}
