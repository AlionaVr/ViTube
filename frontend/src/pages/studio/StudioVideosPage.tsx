import { type ReactNode, useState } from 'react'
import { Link, Navigate, useLocation } from 'react-router'

import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Icon from '../../components/Icon'
import IconButton from '../../components/IconButton'
import MenuChoices, { type MenuChoice } from '../../components/Menu'
import Popover from '../../components/Popover'
import Spinner from '../../components/Spinner'
import Thumbnail from '../../components/Thumbnail'
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll'
import { formatDate, formatExact } from '../../lib/format'
import { VISIBILITY } from '../../playlists/visibility'
import buttons from '../../styles/buttons.module.css'
import EditDetailsDialog from '../../upload/EditDetailsDialog'
import SharePrivatelyDialog from '../../upload/SharePrivatelyDialog'
import UploadDialog from '../../upload/UploadDialog'
import { useMyVideos } from '../../videos/hooks'
import { watchUrl } from '../../videos/paths'
import type { OwnVideo, VideoStatus } from '../../videos/types'
import { useViewer } from '../../viewer/useViewer'
import styles from './StudioVideosPage.module.css'

const SKELETON_ROWS = 6

const STATUS_LABELS: Record<Exclude<VideoStatus, 'uploading' | 'failed'>, string> = {
  uploaded: 'Processing',
  processing: 'Processing',
  ready: 'Ready',
}

/** YouTube Studio's Content page: every video of the signed-in user, whatever its status. */
export default function StudioVideosPage() {
  const viewer = useViewer()
  const location = useLocation()
  const videos = useMyVideos(viewer.status === 'authenticated')
  const [editing, setEditing] = useState<OwnVideo | null>(null)
  const [sharing, setSharing] = useState<OwnVideo | null>(null)
  const [uploading, setUploading] = useState(false)
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => void videos.fetchNextPage(),
    videos.hasNextPage && !videos.isFetchingNextPage && !videos.isFetchNextPageError,
  )

  // As in YouTube Studio: a guest signs in first and comes back here.
  if (viewer.status === 'guest') {
    return <Navigate to="/login" state={{ from: location.pathname + location.search }} replace />
  }
  const items = videos.data?.pages.flatMap((page) => page.items) ?? []

  return (
    <div className={styles.page}>
      <title>Channel content - ViTube</title>
      <div className={styles.top}>
        <h1 className={styles.heading}>Channel content</h1>
        {/* The header's Create dialog: the new draft joins this list. */}
        <button
          type="button"
          className={`${buttons.pill} ${buttons.primary}`}
          onClick={() => setUploading(true)}
        >
          Upload videos
        </button>
      </div>
      {videos.isPending ? (
        <VideoTable label="Loading videos" busy>
          {Array.from({ length: SKELETON_ROWS }, (_, i) => (
            <SkeletonRow key={i} />
          ))}
        </VideoTable>
      ) : !videos.data ? (
        <ErrorState title="Can’t load your videos" onRetry={() => void videos.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState title="No content available">Videos you upload will appear here.</EmptyState>
      ) : (
        <>
          <VideoTable label="Videos">
            {items.map((video) => (
              <VideoRow
                key={video.id}
                video={video}
                onEdit={() => setEditing(video)}
                onShare={() => setSharing(video)}
              />
            ))}
          </VideoTable>
          <div ref={sentinel} />
          {videos.isFetchingNextPage && (
            <div className={styles.more}>
              <Spinner label="Loading more videos" />
            </div>
          )}
          {videos.isFetchNextPageError && (
            <ErrorState
              title="Can’t load more videos"
              onRetry={() => void videos.fetchNextPage()}
            />
          )}
        </>
      )}
      {editing && <EditDetailsDialog video={editing} onClose={() => setEditing(null)} />}
      {sharing && <SharePrivatelyDialog video={sharing} onClose={() => setSharing(null)} />}
      {uploading && <UploadDialog onClose={() => setUploading(false)} />}
    </div>
  )
}

function VideoTable({
  label,
  busy,
  children,
}: {
  label: string
  busy?: boolean
  children: ReactNode
}) {
  return (
    // Studio's columns don't fit a phone: the table scrolls inside, the page doesn't.
    <div className={styles.scroller}>
      <table className={styles.table} aria-label={label} aria-busy={busy}>
        <colgroup>
          <col className={styles.videoColumn} />
          <col className={styles.visibilityColumn} />
          <col className={styles.restrictionsColumn} />
          <col className={styles.statusColumn} />
          <col className={styles.dateColumn} />
          <col className={styles.countColumn} />
          <col className={styles.commentsColumn} />
          <col className={styles.countColumn} />
        </colgroup>
        <thead>
          <tr>
            <th scope="col">Video</th>
            <th scope="col">Visibility</th>
            <th scope="col">Restrictions</th>
            <th scope="col">Status</th>
            <th scope="col">Date</th>
            <th scope="col" className={styles.number}>
              Views
            </th>
            <th scope="col" className={styles.number}>
              Comments
            </th>
            <th scope="col" className={styles.number}>
              Likes
            </th>
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

interface RowActions {
  onEdit: () => void
  onShare: () => void
}

/** Studio's ⋮ on a row, always shown here (not only on hover). */
function RowMenu({ video, onEdit, onShare }: { video: OwnVideo } & RowActions) {
  const label = `Options for ${video.title}`
  const choices: MenuChoice[] = [{ icon: 'edit', label: 'Edit details', onSelect: onEdit }]
  // Grants count only while a video is private (ADR 0004).
  if (video.visibility === 'private') {
    choices.push({ icon: 'personAdd', label: 'Share privately', onSelect: onShare })
  }
  return (
    <Popover
      label={label}
      role="menu"
      align="end"
      trigger={(props) => <IconButton icon="moreVert" label={label} {...props} />}
    >
      {(close) => <MenuChoices choices={choices} close={close} />}
    </Popover>
  )
}

function VideoRow({ video, ...actions }: { video: OwnVideo } & RowActions) {
  const url = watchUrl(video.id)
  return (
    <tr className={styles.row}>
      <td>
        <div className={styles.video}>
          {/* The title is the link for keyboards and screen readers. */}
          <Link to={url} className={styles.thumbnail} tabIndex={-1} aria-hidden="true">
            {video.thumbnail_url && video.duration_sec !== null ? (
              <Thumbnail src={video.thumbnail_url} durationSec={video.duration_sec} compact />
            ) : (
              <div className={styles.placeholder} />
            )}
          </Link>
          <div className={styles.details}>
            <Link to={url} className={styles.title}>
              {video.title}
            </Link>
            {video.description && <p className={styles.description}>{video.description}</p>}
          </div>
          <div className={styles.menu}>
            <RowMenu video={video} {...actions} />
          </div>
        </div>
      </td>
      {/* As in Studio: a draft (no file yet, or its upload was cut off) shows as such here. */}
      <td>
        {video.status === 'uploading' ? (
          'Draft'
        ) : (
          <span className={styles.withIcon}>
            <Icon name={VISIBILITY[video.visibility].icon} size={18} />
            {VISIBILITY[video.visibility].label}
          </span>
        )}
      </td>
      {/* Studio's column; the one restriction here is a moderator's (ADR 0009). */}
      <td>{video.is_hidden ? 'Hidden by a moderator' : 'None'}</td>
      <td>
        <Status video={video} />
      </td>
      <td>
        {formatDate(video.created_at)}
        {/* Studio's wording; the API has one date, the upload's, for both. */}
        <p className={styles.secondary}>
          {video.visibility === 'public' && video.status === 'ready' ? 'Published' : 'Uploaded'}
        </p>
      </td>
      <td className={styles.number}>{formatExact(video.view_count)}</td>
      <td className={styles.number}>{formatExact(video.comment_count)}</td>
      <td className={styles.number}>{formatExact(video.like_count)}</td>
    </tr>
  )
}

function Status({ video }: { video: OwnVideo }) {
  if (video.status === 'uploading') return null // Visibility already says Draft
  if (video.status !== 'failed') return STATUS_LABELS[video.status]
  return (
    <>
      <span className={styles.failed}>
        <Icon name="errorFill" size={18} />
        Processing failed
      </span>
      <p className={styles.secondary}>{video.error_message}</p>
    </>
  )
}

function SkeletonRow() {
  return (
    <tr aria-hidden="true">
      <td>
        <div className={styles.video}>
          <div className={`${styles.thumbnail} ${styles.placeholder}`} />
          <div className={styles.details}>
            <div className={styles.bar} />
            <div className={`${styles.bar} ${styles.short}`} />
          </div>
        </div>
      </td>
      <td colSpan={7} />
    </tr>
  )
}
