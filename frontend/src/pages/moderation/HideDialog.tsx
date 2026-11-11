import { useState } from 'react'

import Dialog from '../../components/Dialog'
import type { ModeratedVideo, ReportReason } from '../../moderation/api'
import { useHideVideo } from '../../moderation/hooks'
import { REASON_LABELS, REASONS } from '../../moderation/reasons'
import buttons from '../../styles/buttons.module.css'
import choices from '../../styles/choices.module.css'
import styles from './ModerationPage.module.css'

export interface HideTarget {
  video: ModeratedVideo
  /** What viewers reported: the first one is offered first. */
  reasons: ReportReason[]
}

/** Asks which rule the video breaks, then hides it. */
export default function HideDialog({
  target,
  onClose,
}: {
  target: HideTarget | null
  onClose: () => void
}) {
  return (
    <Dialog open={target !== null} onClose={onClose} label="Hide video">
      {/* Keyed: each video starts from its own reports' reason. */}
      {target && <HideForm key={target.video.id} target={target} onDone={onClose} />}
    </Dialog>
  )
}

function HideForm({ target, onDone }: { target: HideTarget; onDone: () => void }) {
  const [reason, setReason] = useState<ReportReason>(target.reasons[0] ?? REASONS[0])
  const hide = useHideVideo()

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        hide.mutate({ id: target.video.id, reason }, { onSuccess: onDone })
      }}
    >
      <h2 className={styles.dialogTitle}>Hide video</h2>
      <p className={styles.dialogText}>
        Only the owner and moderators will be able to open “{target.video.title}”. Its reports will
        close.
      </p>
      <fieldset className={choices.list}>
        <legend className={choices.legend}>Rule it breaks</legend>
        {REASONS.map((value) => (
          <label key={value} className={choices.option}>
            <input
              type="radio"
              name="reason"
              value={value}
              checked={reason === value}
              onChange={() => setReason(value)}
            />
            {REASON_LABELS[value]}
          </label>
        ))}
      </fieldset>
      {hide.isError && (
        <p className={styles.error} role="alert">
          {hide.error.message}
        </p>
      )}
      <div className={styles.dialogActions}>
        <button type="button" className={`${buttons.pill} ${buttons.text}`} onClick={onDone}>
          Cancel
        </button>
        <button
          type="submit"
          className={`${buttons.pill} ${buttons.link}`}
          disabled={hide.isPending}
        >
          Hide
        </button>
      </div>
    </form>
  )
}
