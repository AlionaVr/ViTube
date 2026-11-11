import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type CSSProperties, type FormEvent, useId, useRef, useState } from 'react'

import Icon from '../components/Icon'
import IconButton from '../components/IconButton'
import Spinner from '../components/Spinner'
import { useModalDialog } from '../hooks/useModalDialog'
import buttons from '../styles/buttons.module.css'
import { CATEGORIES, CATEGORY_LABELS } from '../videos/categories'
import { videoKeys } from '../videos/hooks'
import { watchUrl } from '../videos/paths'
import type { Category, OwnVideo, Visibility } from '../videos/types'
import { VISIBILITY_LABELS } from '../videos/visibility'
import { updateVideo } from './api'
import { formatLimits } from './format'
import styles from './UploadDialog.module.css'
import { type Transfer, useUpload } from './useUpload'

const TITLE_MAX = 100
const DESCRIPTION_MAX = 5000

const VISIBILITY: { value: Visibility; label: string; hint: string }[] = [
  {
    value: 'private',
    label: VISIBILITY_LABELS.private,
    hint: 'Only you and people you choose can watch your video',
  },
  {
    value: 'unlisted',
    label: VISIBILITY_LABELS.unlisted,
    hint: 'Anyone with the video link can watch your video',
  },
  { value: 'public', label: VISIBILITY_LABELS.public, hint: 'Everyone can watch your video' },
]

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
  const [title, setTitle] = useState(video.title)
  const [description, setDescription] = useState(video.description)
  const [visibility, setVisibility] = useState<Visibility>(video.visibility)
  const [category, setCategory] = useState<Category>(video.category)
  const queryClient = useQueryClient()
  const save = useMutation({
    mutationFn: () => updateVideo(video.id, { title, description, visibility, category }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: videoKeys.mine }),
  })
  const categoryId = useId()
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
          <h3 className={styles.section}>Details</h3>
          <TextArea
            label="Title (required)"
            value={title}
            maxLength={TITLE_MAX}
            rows={2}
            required
            onChange={setTitle}
          />
          <TextArea
            label="Description"
            value={description}
            maxLength={DESCRIPTION_MAX}
            rows={6}
            placeholder="Tell viewers about your video"
            onChange={setDescription}
          />
          <div>
            <h3 className={styles.section}>Category</h3>
            <p className={styles.sectionHint}>
              Add your video to a category so viewers can find it more easily
            </p>
            <div className={`${styles.box} ${styles.selectBox}`}>
              <label htmlFor={categoryId} className={styles.boxLabel}>
                Category
              </label>
              <select
                id={categoryId}
                className={styles.select}
                value={category}
                onChange={(event) => setCategory(event.target.value as Category)}
              >
                {CATEGORIES.map((id) => (
                  <option key={id} value={id}>
                    {CATEGORY_LABELS[id]}
                  </option>
                ))}
              </select>
              <span className={styles.selectArrow}>
                <Icon name="chevronDown" />
              </span>
            </div>
          </div>
          <fieldset className={styles.visibility}>
            <legend className={styles.section}>Visibility</legend>
            <p className={styles.sectionHint}>Choose who can watch your video</p>
            {VISIBILITY.map((option) => (
              <label key={option.value} className={styles.option}>
                <input
                  type="radio"
                  name="visibility"
                  value={option.value}
                  checked={visibility === option.value}
                  onChange={() => setVisibility(option.value)}
                />
                <span>
                  <span className={styles.optionLabel}>{option.label}</span>
                  <span className={styles.optionHint}>{option.hint}</span>
                </span>
              </label>
            ))}
          </fieldset>
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
          disabled={!title.trim() || save.isPending}
        >
          Save
        </button>
      </div>
    </form>
  )
}

function TextArea({
  label,
  value,
  maxLength,
  onChange,
  ...rest
}: {
  label: string
  value: string
  maxLength: number
  rows: number
  required?: boolean
  placeholder?: string
  onChange: (value: string) => void
}) {
  const id = useId()
  return (
    <div className={styles.box}>
      <label htmlFor={id} className={styles.boxLabel}>
        {label}
      </label>
      <textarea
        id={id}
        className={styles.textarea}
        value={value}
        maxLength={maxLength}
        onChange={(event) => onChange(event.target.value)}
        style={{ '--rows': rest.rows } as CSSProperties}
        {...rest}
      />
      <span className={styles.counter} aria-hidden="true">
        {value.length}/{maxLength}
      </span>
    </div>
  )
}

function Preview({ video, transfer }: { video: OwnVideo; transfer: Transfer }) {
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
  const text =
    video.status === 'failed'
      ? 'Processing failed'
      : transfer.phase === 'stored'
        ? 'Processing video…'
        : 'Uploading video…'
  return (
    <div className={`${styles.screen} ${styles.placeholder}`}>
      {transfer.phase === 'stored' && video.status !== 'failed' && (
        <Spinner label="Processing" size={28} />
      )}
      <span>{text}</span>
    </div>
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
