import { Link, Navigate, useSearchParams } from 'react-router'

import Avatar from '../../components/Avatar'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Spinner from '../../components/Spinner'
import Thumbnail from '../../components/Thumbnail'
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll'
import { formatTimeAgo, formatViews } from '../../lib/format'
import type { SearchResult } from '../../search/api'
import { useSearch } from '../../search/hooks'
import { channelUrl, watchUrl } from '../../videos/paths'
import styles from './ResultsPage.module.css'

const SKELETON_ROWS = 6

/** YouTube's result row: the thumbnail beside the details. The title is the one tab stop. */
function Result({ video }: { video: SearchResult }) {
  const { channel } = video
  return (
    <article className={styles.result}>
      <Link to={watchUrl(video.id)} className={styles.thumbnail} tabIndex={-1} aria-hidden="true">
        <Thumbnail src={video.thumbnail_url} durationSec={video.duration_sec} videoId={video.id} />
      </Link>
      <div className={styles.details}>
        <h3 className={styles.title}>
          <Link to={watchUrl(video.id)} title={video.title}>
            {video.title}
          </Link>
        </h3>
        <p className={styles.line}>
          {formatViews(video.view_count)} • {formatTimeAgo(video.created_at)}
        </p>
        <Link to={channelUrl(channel.handle)} className={styles.channel}>
          <Avatar name={channel.name} src={channel.avatar_url} size={24} />
          {channel.name}
        </Link>
        {video.description && <p className={styles.description}>{video.description}</p>}
      </div>
    </article>
  )
}

function ResultSkeleton() {
  return (
    <div className={styles.result} aria-hidden="true">
      <div className={`${styles.thumbnail} ${styles.ghostThumbnail}`} />
      <div className={styles.details}>
        <div className={styles.ghostLine} />
        <div className={`${styles.ghostLine} ${styles.ghostShort}`} />
      </div>
    </div>
  )
}

function Results({ query }: { query: string }) {
  const results = useSearch(query)
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => void results.fetchNextPage(),
    results.hasNextPage && !results.isFetchingNextPage && !results.isFetchNextPageError,
  )

  if (results.isPending) {
    return (
      <div className={styles.list} aria-busy="true" aria-label="Loading results">
        {Array.from({ length: SKELETON_ROWS }, (_, i) => (
          <ResultSkeleton key={i} />
        ))}
      </div>
    )
  }
  if (!results.data) {
    return <ErrorState title="Can’t load results" onRetry={() => void results.refetch()} />
  }
  const videos = results.data.pages.flatMap((page) => page.items)
  if (videos.length === 0) {
    return (
      <EmptyState title="No results found">
        Try different keywords or check the spelling.
      </EmptyState>
    )
  }
  return (
    <>
      <div className={styles.list}>
        {videos.map((video) => (
          <Result key={video.id} video={video} />
        ))}
      </div>
      <div ref={sentinel} />
      {results.isFetchingNextPage && (
        <div className={styles.more}>
          <Spinner label="Loading more results" />
        </div>
      )}
      {results.isFetchNextPageError && (
        <ErrorState title="Can’t load more results" onRetry={() => void results.fetchNextPage()} />
      )}
    </>
  )
}

/** /results?search_query=: YouTube's URL, so its links and habits work here too. */
export default function ResultsPage() {
  const [params] = useSearchParams()
  const query = params.get('search_query')?.trim() ?? ''
  if (!query) return <Navigate to="/" replace />

  return (
    <div className={styles.page}>
      <title>{`${query} - ViTube`}</title>
      {/* A new query starts afresh: no rows or scroll state from the last one. */}
      <Results key={query} query={query} />
    </div>
  )
}
