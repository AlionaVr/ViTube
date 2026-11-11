import { type FormEvent, useState } from 'react'

import Dialog from '../components/Dialog'
import IconButton from '../components/IconButton'
import TextField from '../components/TextField'
import buttons from '../styles/buttons.module.css'
import styles from './EditPlaylistDialog.module.css'
import { useUpdatePlaylist } from './hooks'
import { TITLE_MAX } from './limits'
import { DescriptionField, PrivacySelect } from './PlaylistFields'
import type { Playlist } from './types'

function EditForm({ playlist, onDone }: { playlist: Playlist; onDone: () => void }) {
  const update = useUpdatePlaylist(playlist.id)
  const [title, setTitle] = useState(playlist.title)
  const [description, setDescription] = useState(playlist.description)
  const [visibility, setVisibility] = useState(playlist.visibility)

  async function submit(event: FormEvent) {
    event.preventDefault()
    try {
      await update.mutateAsync({ title, description, visibility })
      onDone()
    } catch {
      // The form stays open with the server's reason below.
    }
  }

  return (
    <form className={styles.form} onSubmit={(event) => void submit(event)}>
      <TextField
        label="Title"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        maxLength={TITLE_MAX}
        hint={`${title.length}/${TITLE_MAX}`}
        autoFocus
        required
      />
      <DescriptionField value={description} onChange={setDescription} />
      <PrivacySelect value={visibility} onChange={setVisibility} />
      {update.isError && (
        <p className={styles.error} role="alert">
          {update.error.message}
        </p>
      )}
      <div className={styles.actions}>
        <button type="button" className={`${buttons.pill} ${buttons.text}`} onClick={onDone}>
          Cancel
        </button>
        <button
          type="submit"
          className={`${buttons.pill} ${buttons.link}`}
          disabled={!title.trim() || update.isPending}
        >
          Save
        </button>
      </div>
    </form>
  )
}

export default function EditPlaylistDialog({
  playlist,
  open,
  onClose,
}: {
  playlist: Playlist
  open: boolean
  onClose: () => void
}) {
  return (
    <Dialog open={open} onClose={onClose} label="Edit playlist">
      <div className={styles.header}>
        <h2 className={styles.title}>Edit playlist</h2>
        <IconButton icon="close" label="Close" onClick={onClose} />
      </div>
      {/* Mounted only while open: each opening starts from the playlist as it is. */}
      {open && <EditForm playlist={playlist} onDone={onClose} />}
    </Dialog>
  )
}
