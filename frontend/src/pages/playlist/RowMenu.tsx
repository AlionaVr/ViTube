import { Menu, type MenuChoice } from '../../components/Menu'
import { useVideoChoices, type VideoDialog } from '../../videos/useVideoChoices'

/** What the list's owner can do to a row. */
export interface ItemActions {
  remove: () => void
  /** Missing on the first item. */
  moveToTop?: () => void
  /** Missing on the last item. */
  moveToBottom?: () => void
}

/** Opens the page's one Save or Share dialog: the row may leave while it is open. */
export type OpenDialog = (dialog: VideoDialog, videoId: string) => void

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
  const choices: MenuChoice[] = useVideoChoices(
    videoId,
    (dialog) => openDialog(dialog, videoId),
    watchLater,
  )
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
