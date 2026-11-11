import { useState } from 'react'

import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Spinner from '../../components/Spinner'
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll'
import { formatTimeAgo } from '../../lib/format'
import type { Account, ModeratedComment, ModeratedVideo, ReportCase } from '../../moderation/api'
import { useDismissComment, useDismissVideo, useReportQueue } from '../../moderation/hooks'
import { REASON_LABELS } from '../../moderation/reasons'
import { isAdmin } from '../../moderation/roles'
import buttons from '../../styles/buttons.module.css'
import CommentCell from './CommentCell'
import DeleteCommentDialog from './DeleteCommentDialog'
import HideDialog, { type HideTarget } from './HideDialog'
import styles from './ModerationPage.module.css'
import RestrictDialog from './RestrictDialog'
import RowMenu from './RowMenu'
import { useModerator } from './useModerator'
import VideoCell, { OwnNote } from './VideoCell'

/** Open reports, one row per video or comment, oldest first: the order moderators work in. */
export default function ReportQueue() {
  const queue = useReportQueue()
  const [hiding, setHiding] = useState<HideTarget | null>(null)
  const [deleting, setDeleting] = useState<ModeratedComment | null>(null)
  const [restricting, setRestricting] = useState<Account | null>(null)
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
      <ol className={styles.rows} aria-label="Reports">
        {cases.map((reportCase) =>
          reportCase.video ? (
            <VideoCaseRow
              key={reportCase.video.id}
              video={reportCase.video}
              reportCase={reportCase}
              onHide={setHiding}
              onRestrict={setRestricting}
            />
          ) : (
            reportCase.comment && (
              <CommentCaseRow
                key={reportCase.comment.id}
                comment={reportCase.comment}
                reportCase={reportCase}
                onDelete={setDeleting}
                onRestrict={setRestricting}
              />
            )
          ),
        )}
      </ol>
      <div ref={sentinel} />
      {queue.isFetchingNextPage && (
        <div className={styles.loading}>
          <Spinner />
        </div>
      )}
      <HideDialog target={hiding} onClose={() => setHiding(null)} />
      <DeleteCommentDialog target={deleting} onClose={() => setDeleting(null)} />
      <RestrictDialog target={restricting} onClose={() => setRestricting(null)} />
    </>
  )
}

function VideoCaseRow({
  video,
  reportCase,
  onHide,
  onRestrict,
}: {
  video: ModeratedVideo
  reportCase: ReportCase
  onHide: (target: HideTarget) => void
  onRestrict: (account: Account) => void
}) {
  const moderator = useModerator()
  const own = video.channel.handle === moderator.handle
  const dismiss = useDismissVideo()
  return (
    <li className={`${styles.row} ${styles.withReports}`}>
      <VideoCell video={video} />
      <ReportsCell reportCase={reportCase} />
      <div className={styles.actions}>
        {own ? (
          <OwnNote what="video" />
        ) : (
          <>
            <button
              type="button"
              className={`${buttons.pill} ${buttons.tonal} ${buttons.small}`}
              aria-haspopup="dialog"
              aria-label={`Hide “${video.title}”`}
              onClick={() => onHide({ video, reasons: reportCase.reasons })}
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
            {isAdmin(moderator) && (
              <RowMenu account={video.channel} onRestrict={() => onRestrict(video.channel)} />
            )}
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

function CommentCaseRow({
  comment,
  reportCase,
  onDelete,
  onRestrict,
}: {
  comment: ModeratedComment
  reportCase: ReportCase
  onDelete: (target: ModeratedComment) => void
  onRestrict: (account: Account) => void
}) {
  const moderator = useModerator()
  const own = comment.author.handle === moderator.handle
  const dismiss = useDismissComment()
  const label = `comment by @${comment.author.handle}`
  return (
    <li className={`${styles.row} ${styles.withReports}`}>
      <CommentCell comment={comment} />
      <ReportsCell reportCase={reportCase} />
      <div className={styles.actions}>
        {own ? (
          <OwnNote what="comment" />
        ) : (
          <>
            <button
              type="button"
              className={`${buttons.pill} ${buttons.tonal} ${buttons.small}`}
              aria-haspopup="dialog"
              aria-label={`Delete ${label}`}
              onClick={() => onDelete(comment)}
            >
              Delete
            </button>
            <button
              type="button"
              className={`${buttons.pill} ${buttons.text} ${buttons.small}`}
              aria-label={`Dismiss reports of ${label}`}
              disabled={dismiss.isPending}
              onClick={() => dismiss.mutate({ id: comment.id, videoId: comment.video.id })}
            >
              Dismiss
            </button>
            {isAdmin(moderator) && (
              <RowMenu account={comment.author} onRestrict={() => onRestrict(comment.author)} />
            )}
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

/** How many reported it, why, and what they wrote. */
function ReportsCell({ reportCase }: { reportCase: ReportCase }) {
  const count = reportCase.report_count
  return (
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
  )
}
