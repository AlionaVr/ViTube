import { useState } from 'react'
import { useNavigate } from 'react-router'

import Dialog from '../../components/Dialog'
import Icon, { type IconName } from '../../components/Icon'
import IconButton from '../../components/IconButton'
import Popover from '../../components/Popover'
import { useToast } from '../../hooks/useToast'
import EditPlaylistDialog from '../../playlists/EditPlaylistDialog'
import { useDeletePlaylist } from '../../playlists/hooks'
import type { Playlist } from '../../playlists/types'
import buttons from '../../styles/buttons.module.css'
import styles from './OwnerTools.module.css'

interface MenuChoice {
  icon: IconName
  label: string
  onSelect: () => void
}

/** YouTube's ⋮ menu: icon and label per line. */
function Menu({
  label,
  choices,
  light,
}: {
  label: string
  choices: MenuChoice[]
  light?: boolean
}) {
  return (
    <Popover
      label={label}
      role="menu"
      align={light ? 'start' : 'end'}
      trigger={(props) => (
        <IconButton
          icon="moreVert"
          label={label}
          className={light ? styles.light : undefined}
          {...props}
        />
      )}
    >
      {(close) => (
        <div className={styles.menu}>
          {choices.map((choice) => (
            <button
              key={choice.label}
              type="button"
              role="menuitem"
              className={styles.choice}
              onClick={() => {
                close()
                choice.onSelect()
              }}
            >
              <Icon name={choice.icon} />
              {choice.label}
            </button>
          ))}
        </div>
      )}
    </Popover>
  )
}

function DeleteDialog({
  playlist,
  open,
  onClose,
}: {
  playlist: Playlist
  open: boolean
  onClose: () => void
}) {
  const remove = useDeletePlaylist()
  const navigate = useNavigate()
  const toast = useToast()

  async function confirm() {
    try {
      await remove.mutateAsync(playlist.id)
    } catch {
      return // the dialog stays open with the reason
    }
    void navigate('/feed/playlists')
    toast('Playlist deleted')
  }

  return (
    <Dialog open={open} onClose={onClose} label="Delete playlist">
      <h2 className={styles.heading}>Delete playlist</h2>
      <p className={styles.text}>
        Are you sure you want to delete <strong>{playlist.title}</strong>?
      </p>
      <p className={styles.note}>
        Note: Deleting playlists is a permanent action and cannot be undone.
      </p>
      {remove.isError && (
        <p className={styles.error} role="alert">
          {remove.error.message}
        </p>
      )}
      <div className={styles.actions}>
        <button type="button" className={`${buttons.pill} ${buttons.text}`} onClick={onClose}>
          Cancel
        </button>
        <button
          type="button"
          className={`${buttons.pill} ${buttons.link}`}
          disabled={remove.isPending}
          onClick={() => void confirm()}
        >
          Delete
        </button>
      </div>
    </Dialog>
  )
}

/** The owner's round buttons on the playlist panel: edit, and ⋮ with delete. */
export function PlaylistTools({ playlist }: { playlist: Playlist }) {
  const [dialog, setDialog] = useState<'edit' | 'delete' | null>(null)
  const close = () => setDialog(null)
  return (
    <div className={styles.tools}>
      <IconButton
        icon="edit"
        label="Edit playlist"
        className={styles.light}
        aria-haspopup="dialog"
        onClick={() => setDialog('edit')}
      />
      <Menu
        label="More actions"
        light
        choices={[
          { icon: 'delete', label: 'Delete playlist', onSelect: () => setDialog('delete') },
        ]}
      />
      <EditPlaylistDialog playlist={playlist} open={dialog === 'edit'} onClose={close} />
      <DeleteDialog playlist={playlist} open={dialog === 'delete'} onClose={close} />
    </div>
  )
}

export interface ItemActions {
  remove: () => void
  /** Missing on the first item. */
  moveToTop?: () => void
  /** Missing on the last item. */
  moveToBottom?: () => void
}

/** ⋮ on a video of the owner's playlist. */
export function ItemMenu({ playlist, actions }: { playlist: Playlist; actions: ItemActions }) {
  const choices: MenuChoice[] = [
    { icon: 'delete', label: `Remove from ${playlist.title}`, onSelect: actions.remove },
  ]
  if (actions.moveToTop) {
    choices.push({ icon: 'moveTop', label: 'Move to top', onSelect: actions.moveToTop })
  }
  if (actions.moveToBottom) {
    choices.push({ icon: 'moveBottom', label: 'Move to bottom', onSelect: actions.moveToBottom })
  }
  return <Menu label="Action menu" choices={choices} />
}
