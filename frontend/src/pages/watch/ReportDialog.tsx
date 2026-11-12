import { useState } from 'react'

import Dialog from '../../components/Dialog'
import type { ReportReason, ReportTarget } from '../../moderation/api'
import { useReport } from '../../moderation/hooks'
import { REASON_LABELS, REASONS } from '../../moderation/reasons'
import buttons from '../../styles/buttons.module.css'
import choices from '../../styles/choices.module.css'
import styles from './ReportDialog.module.css'

const DETAILS_MAX = 500 // the API's limit, as on YouTube

/** YouTube's report flow: a reason, then (for a video) optional details, then thanks. */
export default function ReportDialog({
  target,
  open,
  onClose,
}: {
  target: ReportTarget
  open: boolean
  onClose: () => void
}) {
  return (
    <Dialog open={open} onClose={onClose} label={`Report ${target.kind}`}>
      {/* Mounted per opening: each report starts afresh. */}
      {open && <ReportFlow target={target} onDone={onClose} />}
    </Dialog>
  )
}

function ReportFlow({ target, onDone }: { target: ReportTarget; onDone: () => void }) {
  const [step, setStep] = useState<'reason' | 'details' | 'thanks'>('reason')
  const [reason, setReason] = useState<ReportReason | null>(null)
  const [details, setDetails] = useState('')
  const report = useReport()
  const next = step === 'reason' && target.kind === 'video' // a video asks for details next

  if (step === 'thanks') {
    return (
      <>
        <h2 className={styles.title}>Thanks for reporting</h2>
        <p className={styles.text}>
          Moderators will check it. If it breaks the rules, they’ll remove it.
        </p>
        <div className={styles.actions}>
          <button type="button" className={`${buttons.pill} ${buttons.link}`} onClick={onDone}>
            Close
          </button>
        </div>
      </>
    )
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        if (next) setStep('details')
        else if (reason) {
          report.mutate({ target, reason, details }, { onSuccess: () => setStep('thanks') })
        }
      }}
    >
      <h2 className={styles.title}>Report {target.kind}</h2>
      {step === 'reason' ? (
        <fieldset className={choices.list}>
          <legend className={styles.question}>What’s going on?</legend>
          <p className={styles.text}>
            Moderators check it against all the rules, so don’t worry about picking the right one.
          </p>
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
      ) : (
        <label className={styles.details}>
          <span className={styles.question}>Want to tell us more? It’s optional</span>
          <textarea
            value={details}
            maxLength={DETAILS_MAX}
            rows={4}
            placeholder="Add details…"
            onChange={(event) => setDetails(event.target.value)}
          />
          <span className={styles.counter}>
            {details.length}/{DETAILS_MAX}
          </span>
        </label>
      )}
      {report.isError && (
        <p className={styles.error} role="alert">
          {report.error.message}
        </p>
      )}
      <div className={styles.actions}>
        {step === 'details' ? (
          <button
            type="button"
            className={`${buttons.pill} ${buttons.text}`}
            onClick={() => setStep('reason')}
          >
            Back
          </button>
        ) : (
          <button type="button" className={`${buttons.pill} ${buttons.text}`} onClick={onDone}>
            Cancel
          </button>
        )}
        <button
          type="submit"
          className={`${buttons.pill} ${buttons.link}`}
          disabled={reason === null || report.isPending}
        >
          {next ? 'Next' : 'Report'}
        </button>
      </div>
    </form>
  )
}
