import { useQueryClient } from '@tanstack/react-query'

import type { MenuChoice } from '../components/Menu'
import { useToast } from '../hooks/useToast'
import { useSetInPlaylist, watchLaterQuery } from '../playlists/hooks'
import { NOT_SAVED } from '../playlists/SaveDialog'
import { useViewer } from '../viewer/useViewer'

export type VideoDialog = 'save' | 'share'

/** The start of YouTube's ⋮ menu for a video: Save and Share. A guest gets Share only.
 * `inWatchLater`: the video is listed in Watch later, so saving there is no choice. */
export function useVideoChoices(
  videoId: string,
  openDialog: (dialog: VideoDialog) => void,
  inWatchLater = false,
): MenuChoice[] {
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
  if (signedIn && !inWatchLater) {
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
      onSelect: () => openDialog('save'),
    })
  }
  choices.push({ icon: 'share', label: 'Share', onSelect: () => openDialog('share') })
  return choices
}
