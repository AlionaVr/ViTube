import { useLayoutEffect, useRef } from 'react'
import { Link } from 'react-router'

import ErrorState from '../../components/ErrorState'
import Icon from '../../components/Icon'
import Spinner from '../../components/Spinner'
import Thumbnail from '../../components/Thumbnail'
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll'
import { watchUrl } from '../../videos/paths'
import styles from './PlaylistPanel.module.css'
import type { PlayingList } from './usePlaylistQueue'

/** YouTube's playlist panel on the watch page: the list with the current video marked. */
export default function PlaylistPanel({ queue }: { queue: PlayingList }) {
  const { list, videos, position, items } = queue
  const current = position === null ? undefined : videos[position].id
  const rows = useRef<HTMLOListElement>(null)
  // The panel scrolls itself; the sentinel inside it shows only near the end of its rows.
  const sentinel = useInfiniteScroll<HTMLLIElement>(
    () => void items.fetchNextPage(),
    items.hasNextPage && !items.isFetchingNextPage && !items.isFetchNextPageError,
  )

  // The current row at the top of the panel; scrollIntoView would move the page too.
  useLayoutEffect(() => {
    const row = rows.current?.querySelector<HTMLElement>('[aria-current]')
    if (rows.current && row) rows.current.scrollTop = row.offsetTop
  }, [current])

  return (
    <section className={styles.panel} aria-label={queue.title}>
      <div className={styles.header}>
        <h2 className={styles.title}>
          <Link to={queue.url}>{queue.title}</Link>
        </h2>
        <p className={styles.meta}>
          {queue.owner.name}
          {position !== null && ` • ${position + 1} / ${queue.total}`}
        </p>
      </div>
      <ol ref={rows} className={styles.rows}>
        {videos.map((video, index) => {
          const playing = video.id === current
          return (
            <li key={video.id}>
              <Link
                to={watchUrl(video.id, { list })}
                className={styles.row}
                aria-current={playing ? 'true' : undefined}
              >
                <span className={styles.index}>
                  {playing ? <Icon name="play" size={16} /> : index + 1}
                </span>
                <div className={styles.thumbnail}>
                  <Thumbnail
                    src={video.thumbnail_url}
                    durationSec={video.duration_sec}
                    videoId={video.id}
                    compact
                  />
                </div>
                <div className={styles.text}>
                  <h3 className={styles.rowTitle} title={video.title}>
                    {video.title}
                  </h3>
                  <p className={styles.channel}>{video.channel.name}</p>
                </div>
              </Link>
            </li>
          )
        })}
        <li ref={sentinel} aria-hidden="true" />
        {items.isFetchingNextPage && (
          <li>
            <Spinner label="Loading more videos" />
          </li>
        )}
        {items.isFetchNextPageError && (
          <li>
            <ErrorState title="Can’t load more videos" onRetry={() => void items.fetchNextPage()} />
          </li>
        )}
      </ol>
    </section>
  )
}
