import { useQueryClient } from '@tanstack/react-query'

import type { MenuChoice } from '../../components/Menu'
import { useToast } from '../../hooks/useToast'
import { useSetInPlaylist, watchLaterQuery } from '../../playlists/hooks'
import { NOT_SAVED } from '../../playlists/SaveDialog'
import { useViewer } from '../../viewer/useViewer'
import { Menu } from './OwnerTools'

/** What the list's owner can do to a row. */
export interface ItemActions {
  remove: () => void
  /** Missing on the first item. */
  moveToTop?: () => void
  /** Missing on the last item. */
  moveToBottom?: () => void
}

/** Opens the page's one Save or Share dialog: the row may leave while it is open. */
export type OpenDialog = (dialog: 'save' | 'share', videoId: string) => void

/** ⋮ on a playlist row, as YouTube's: save and share, then the list's own actions. */
export function RowMenu({
  videoId,
  title,
  watchLater = false,
  actions,
  openDialog,
}: {
  videoId: string
  /** The list's title, for "Remove from …". */
  title: string
  /** The list is Watch later, so saving to it is no choice. */
  watchLater?: boolean
  actions?: ItemActions
  openDialog: OpenDialog
}) {
  const signedIn = useViewer().status === 'authenticated'
  const queryClient = useQueryClient()
  const save = useSetInPlaylist(videoId)
  const toast = useToast()

  async function saveToWatchLater() {
    try {
      const list = await queryClient.ensureQueryData(watchLaterQuery)
      await save.mutateAsync({ playlistId: list.id, saved: true })
      toast(`Saved to ${list.title}`)
    } catch {
      toast(NOT_SAVED)
    }
  }

  const choices: MenuChoice[] = []
  if (signedIn && !watchLater) {
    choices.push({
      icon: 'watchLater',
      label: 'Save to Watch later',
      onSelect: () => void saveToWatchLater(),
    })
  }
  if (signedIn) {
    choices.push({
      icon: 'bookmark',
      label: 'Save to playlist',
      onSelect: () => openDialog('save', videoId),
    })
  }
  choices.push({ icon: 'share', label: 'Share', onSelect: () => openDialog('share', videoId) })
  if (actions) {
    choices.push({ icon: 'delete', label: `Remove from ${title}`, onSelect: actions.remove })
    if (actions.moveToTop) {
      choices.push({ icon: 'moveTop', label: 'Move to top', onSelect: actions.moveToTop })
    }
    if (actions.moveToBottom) {
      choices.push({ icon: 'moveBottom', label: 'Move to bottom', onSelect: actions.moveToBottom })
    }
  }
  return <Menu label="Action menu" choices={choices} />
}
