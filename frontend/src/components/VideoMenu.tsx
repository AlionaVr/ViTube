import { useState } from 'react'

import SaveDialog from '../playlists/SaveDialog'
import ShareDialog from '../videos/ShareDialog'
import { useVideoChoices, type VideoDialog } from '../videos/useVideoChoices'
import { Menu } from './Menu'

/** ⋮ on a video card. Its dialogs open from here: a card stays while they are open. */
export default function VideoMenu({ videoId, className }: { videoId: string; className?: string }) {
  const [dialog, setDialog] = useState<VideoDialog | null>(null)
  // Mounted at the first choice, then kept: closing through <dialog> gives the focus back to ⋮.
  const [used, setUsed] = useState(false)
  const choices = useVideoChoices(videoId, (kind) => {
    setUsed(true)
    setDialog(kind)
  })
  const close = () => setDialog(null)

  return (
    <div className={className}>
      <Menu label="Action menu" choices={choices} />
      {used && (
        <>
          <SaveDialog videoId={videoId} open={dialog === 'save'} onClose={close} />
          <ShareDialog videoId={videoId} open={dialog === 'share'} onClose={close} />
        </>
      )}
    </div>
  )
}
