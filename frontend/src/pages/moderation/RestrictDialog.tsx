import { useState } from 'react'

import type { Account } from '../../moderation/api'
import Dialog from '../../components/Dialog'
import { useSetStatus } from '../../moderation/hooks'
import buttons from '../../styles/buttons.module.css'
import choices from '../../styles/choices.module.css'
import styles from './ModerationPage.module.css'

const REASON_MAX = 500

const CHOICES = [
  {
    status: 'banned',
    label: 'Ban',
    hint: "They can't sign in or do anything. Their videos and comments stay.",
  },
  {
    status: 'terminated',
    label: 'Terminate channel',
    hint: "They can't sign in, and their videos are gone for everyone but moderators.",
  },
] as const

type Choice = (typeof CHOICES)[number]['status']

/** Admins only: ban the account behind a reported video or comment, or end its channel. */
export default function RestrictDialog({
  target,
  onClose,
}: {
  target: Account | null
  onClose: () => void
}) {
  return (
    <Dialog open={target !== null} onClose={onClose} label="Restrict account">
      {target && <RestrictForm key={target.handle} target={target} onDone={onClose} />}
    </Dialog>
  )
}

function RestrictForm({ target, onDone }: { target: Account; onDone: () => void }) {
  const [status, setStatus] = useState<Choice>('banned')
  const [reason, setReason] = useState('')
  const restrict = useSetStatus()

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        restrict.mutate({ handle: target.handle, status, reason }, { onSuccess: onDone })
      }}
    >
      <h2 className={styles.dialogTitle}>Restrict @{target.handle}</h2>
      <p className={styles.dialogText}>Their sessions end at once. You can reinstate them later.</p>
      <fieldset className={choices.list}>
        <legend className={choices.legend}>What happens</legend>
        {CHOICES.map((choice) => (
          <label key={choice.status} className={`${choices.option} ${choices.withHint}`}>
            <input
              type="radio"
              name="status"
              value={choice.status}
              checked={status === choice.status}
              onChange={() => setStatus(choice.status)}
            />
            <span>
              <span className={choices.label}>{choice.label}</span>
              <span className={choices.hint}>{choice.hint}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <label className={styles.reasonField}>
        <span className={choices.legend}>Reason for the audit log</span>
        <textarea
          value={reason}
          maxLength={REASON_MAX}
          rows={2}
          onChange={(event) => setReason(event.target.value)}
        />
      </label>
      {restrict.isError && (
        <p className={styles.error} role="alert">
          {restrict.error.message}
        </p>
      )}
      <div className={styles.dialogActions}>
        <button type="button" className={`${buttons.pill} ${buttons.text}`} onClick={onDone}>
          Cancel
        </button>
        <button
          type="submit"
          className={`${buttons.pill} ${buttons.link}`}
          disabled={restrict.isPending}
        >
          {status === 'banned' ? 'Ban' : 'Terminate'}
        </button>
      </div>
    </form>
  )
}
