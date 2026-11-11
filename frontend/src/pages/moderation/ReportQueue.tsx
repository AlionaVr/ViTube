import { useState } from 'react'

import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Spinner from '../../components/Spinner'
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll'
import { formatTimeAgo } from '../../lib/format'
import type { ReportCase } from '../../moderation/api'
import { useDismissVideo, useReportQueue } from '../../moderation/hooks'
import { REASON_LABELS } from '../../moderation/reasons'
import buttons from '../../styles/buttons.module.css'
import HideDialog from './HideDialog'
import styles from './ModerationPage.module.css'
import { useModerator } from './useModerator'
import VideoCell, { OwnVideoNote } from './VideoCell'

/** Open reports, one row per video, oldest first: the order moderators work through them. */
export default function ReportQueue() {
  const queue = useReportQueue()
  const [hiding, setHiding] = useState<ReportCase | null>(null)
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => queue.fetchNextPage(),
    queue.hasNextPage && !queue.isFetchingNextPage,
  )

  if (queue.isPending) {
    return (
      <div className={styles.loading}>
        <Spinner />
      </div>
    )
  }
  if (queue.isError) {
    return <ErrorState title="Couldn't load reports" onRetry={() => queue.refetch()} />
  }
  const cases = queue.data.pages.flatMap((page) => page.items)
  if (cases.length === 0) {
    return <EmptyState title="No open reports">Reports from viewers show up here.</EmptyState>
  }

  return (
    <>
      <ol className={styles.rows} aria-label="Reported videos">
        {cases.map((reportCase) => (
          <CaseRow
            key={reportCase.video.id}
            reportCase={reportCase}
            onHide={() => setHiding(reportCase)}
          />
        ))}
      </ol>
      <div ref={sentinel} />
      {queue.isFetchingNextPage && (
        <div className={styles.loading}>
          <Spinner />
        </div>
      )}
      <HideDialog target={hiding} onClose={() => setHiding(null)} />
    </>
  )
}

function CaseRow({ reportCase, onHide }: { reportCase: ReportCase; onHide: () => void }) {
  const { video, report_count: count } = reportCase
  const own = video.channel.handle === useModerator().handle
  const dismiss = useDismissVideo()
  return (
    <li className={`${styles.row} ${styles.withReports}`}>
      <VideoCell video={video} />
      <div className={styles.reports}>
        <p className={styles.count}>{count === 1 ? '1 report' : `${count} reports`}</p>
        <ul className={styles.reasons}>
          {reportCase.reasons.map((reason) => (
            <li key={reason}>{REASON_LABELS[reason]}</li>
          ))}
        </ul>
        {reportCase.notes.map((note, index) => (
          <blockquote key={index} className={styles.note}>
            {note}
          </blockquote>
        ))}
        <p className={styles.meta}>Last report {formatTimeAgo(reportCase.last_reported_at)}</p>
      </div>
      <div className={styles.actions}>
        {own ? (
          <OwnVideoNote />
        ) : (
          <>
            <button
              type="button"
              className={`${buttons.pill} ${buttons.tonal} ${buttons.small}`}
              aria-haspopup="dialog"
              aria-label={`Hide “${video.title}”`}
              onClick={onHide}
            >
              Hide
            </button>
            <button
              type="button"
              className={`${buttons.pill} ${buttons.text} ${buttons.small}`}
              aria-label={`Dismiss reports of “${video.title}”`}
              disabled={dismiss.isPending}
              onClick={() => dismiss.mutate({ id: video.id })}
            >
              Dismiss
            </button>
          </>
        )}
        {dismiss.isError && (
          <p className={styles.error} role="alert">
            {dismiss.error.message}
          </p>
        )}
      </div>
    </li>
  )
}
