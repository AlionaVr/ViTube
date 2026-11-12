import { type FormEvent, useState } from 'react'

import { HANDLE } from '../channels/handle'
import Avatar from '../components/Avatar'
import Dialog from '../components/Dialog'
import IconButton from '../components/IconButton'
import Spinner from '../components/Spinner'
import TextField from '../components/TextField'
import { useToast } from '../hooks/useToast'
import buttons from '../styles/buttons.module.css'
import type { OwnVideo } from '../videos/types'
import styles from './SharePrivatelyDialog.module.css'
import { useSetShared, useSharedWith } from './useSharing'

function ShareForm({ video }: { video: OwnVideo }) {
  const [handle, setHandle] = useState('')
  const [invalid, setInvalid] = useState(false)
  const share = useSetShared(video.id)
  const toast = useToast()

  async function submit(event: FormEvent) {
    event.preventDefault()
    const typed = handle.trim().replace(/^@/, '')
    if (!HANDLE.test(typed)) {
      setInvalid(true)
      return
    }
    try {
      await share.mutateAsync({ handle: typed, shared: true })
      setHandle('')
      toast(`Shared with @${typed}`)
    } catch {
      // The server's reason shows under the field.
    }
  }

  const error = invalid
    ? 'Enter a handle such as @anna'
    : share.isError
      ? share.error.message
      : undefined
  return (
    <form className={styles.form} onSubmit={(event) => void submit(event)}>
      <TextField
        label="Handle"
        value={handle}
        onChange={(event) => {
          setHandle(event.target.value)
          setInvalid(false)
          share.reset()
        }}
        error={error}
        hint="Only people you add can watch this private video"
        autoComplete="off"
        autoFocus
      />
      <button
        type="submit"
        className={`${buttons.pill} ${buttons.tonal}`}
        disabled={!handle.trim() || share.isPending}
      >
        Share
      </button>
    </form>
  )
}

function People({ video }: { video: OwnVideo }) {
  const people = useSharedWith(video.id)
  const remove = useSetShared(video.id)
  const toast = useToast()

  async function unshare(handle: string) {
    try {
      await remove.mutateAsync({ handle, shared: false })
      toast(`Removed @${handle}`)
    } catch {
      toast(`Couldn’t remove @${handle}`)
    }
  }

  if (people.isPending) return <Spinner label="Loading people" />
  if (people.isError) {
    return (
      <p className={styles.note} role="alert">
        {people.error.message}
      </p>
    )
  }
  if (!people.data.length) return <p className={styles.note}>Only you can watch this video.</p>
  return (
    <ul className={styles.people} aria-label="Shared with">
      {people.data.map((person) => (
        <li key={person.handle} className={styles.person}>
          <Avatar name={person.name} src={person.avatar_url} size={32} />
          <span className={styles.handle}>@{person.handle}</span>
          <IconButton
            icon="personRemove"
            label={`Remove @${person.handle}`}
            disabled={remove.isPending}
            onClick={() => void unshare(person.handle)}
          />
        </li>
      ))}
    </ul>
  )
}

/** Who may watch a private video besides its owner: add by @handle, remove from the list.
 * Mounted while open: each opening starts with an empty field and a fresh list. */
export default function SharePrivatelyDialog({
  video,
  onClose,
}: {
  video: OwnVideo
  onClose: () => void
}) {
  return (
    <Dialog open onClose={onClose} label="Share privately">
      <div className={styles.header}>
        <h2 className={styles.title}>Share privately</h2>
        <IconButton icon="close" label="Close" onClick={onClose} />
      </div>
      <ShareForm video={video} />
      <h3 className={styles.section}>Shared with</h3>
      <People video={video} />
      <div className={styles.actions}>
        <button type="button" className={`${buttons.pill} ${buttons.link}`} onClick={onClose}>
          Done
        </button>
      </div>
    </Dialog>
  )
}
