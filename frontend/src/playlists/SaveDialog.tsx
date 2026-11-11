import { type FormEvent, useState } from 'react'

import { messageOf } from '../api/client'
import Dialog from '../components/Dialog'
import ErrorState from '../components/ErrorState'
import Icon from '../components/Icon'
import IconButton from '../components/IconButton'
import Spinner from '../components/Spinner'
import TextField from '../components/TextField'
import { useInfiniteScroll } from '../hooks/useInfiniteScroll'
import buttons from '../styles/buttons.module.css'
import { useCreatePlaylist, useMyPlaylists, useSetInPlaylist } from './hooks'
import { TITLE_MAX } from './limits'
import styles from './SaveDialog.module.css'
import type { Visibility } from './types'
import { VISIBILITY } from './visibility'

function NewPlaylistForm({ videoId, onDone }: { videoId: string; onDone: () => void }) {
  const create = useCreatePlaylist()
  const save = useSetInPlaylist(videoId)
  const [title, setTitle] = useState('')
  const [visibility, setVisibility] = useState<Visibility>('private')

  async function submit(event: FormEvent) {
    event.preventDefault()
    try {
      const playlist = await create.mutateAsync({ title, description: '', visibility })
      save.mutate({ playlistId: playlist.id, saved: true })
      onDone()
    } catch {
      // The form stays open with the server's reason below.
    }
  }

  return (
    <form className={styles.form} onSubmit={(event) => void submit(event)}>
      <TextField
        label="Name"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        maxLength={TITLE_MAX}
        hint={`${title.length}/${TITLE_MAX}`}
        error={create.isError ? (messageOf(create.error) ?? create.error.message) : undefined}
        autoFocus
        required
      />
      <label className={styles.privacy}>
        <span>Privacy</span>
        <select
          value={visibility}
          onChange={(event) => setVisibility(event.target.value as Visibility)}
        >
          {(['private', 'unlisted', 'public'] as const).map((value) => (
            <option key={value} value={value}>
              {VISIBILITY[value].label}
            </option>
          ))}
        </select>
      </label>
      <div className={styles.actions}>
        <button
          type="submit"
          className={`${buttons.pill} ${buttons.link}`}
          disabled={!title.trim() || create.isPending}
        >
          Create
        </button>
      </div>
    </form>
  )
}

function Playlists({ videoId }: { videoId: string }) {
  const mine = useMyPlaylists(videoId)
  const save = useSetInPlaylist(videoId)
  const sentinel = useInfiniteScroll<HTMLLIElement>(
    () => void mine.fetchNextPage(),
    mine.hasNextPage && !mine.isFetchingNextPage && !mine.isFetchNextPageError,
  )

  if (mine.isPending) return <Spinner label="Loading your playlists" />
  if (!mine.data) {
    return <ErrorState title="Can’t load your playlists" onRetry={() => void mine.refetch()} />
  }
  const playlists = mine.data.pages.flatMap((page) => page.items)
  if (playlists.length === 0) return null
  return (
    <ul className={styles.list} aria-label="Your playlists">
      {playlists.map((playlist) => {
        const { label, icon } = VISIBILITY[playlist.visibility]
        return (
          <li key={playlist.id}>
            <label className={styles.row}>
              <input
                type="checkbox"
                className={styles.check}
                checked={playlist.contains_video ?? false}
                onChange={(event) =>
                  save.mutate({ playlistId: playlist.id, saved: event.target.checked })
                }
              />
              <span className={styles.name}>{playlist.title}</span>
              <span className={styles.visibility} role="img" aria-label={label} title={label}>
                <Icon name={icon} size={20} />
              </span>
            </label>
          </li>
        )
      })}
      <li ref={sentinel} aria-hidden="true" />
    </ul>
  )
}

interface SaveDialogProps {
  videoId: string
  open: boolean
  onClose: () => void
}

/** YouTube's "Save video to...": tick playlists, or create one with the video in it. */
export default function SaveDialog({ videoId, open, onClose }: SaveDialogProps) {
  const [creating, setCreating] = useState(false)

  function close() {
    setCreating(false)
    onClose()
  }

  return (
    <Dialog open={open} onClose={close} label="Save video to...">
      <div className={styles.header}>
        <h2 className={styles.title}>Save video to...</h2>
        <IconButton icon="close" label="Close" onClick={close} />
      </div>
      {/* Mounted only while open: the list is fetched fresh each time. */}
      {open && <Playlists videoId={videoId} />}
      {creating ? (
        <NewPlaylistForm videoId={videoId} onDone={() => setCreating(false)} />
      ) : (
        <button type="button" className={styles.create} onClick={() => setCreating(true)}>
          <Icon name="add" />
          Create new playlist
        </button>
      )}
    </Dialog>
  )
}
