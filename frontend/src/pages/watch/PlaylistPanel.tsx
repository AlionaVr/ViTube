import { useLayoutEffect, useRef } from 'react'
import { Link, useSearchParams } from 'react-router'

import ErrorState from '../../components/ErrorState'
import Icon from '../../components/Icon'
import IconButton from '../../components/IconButton'
import Spinner from '../../components/Spinner'
import Thumbnail from '../../components/Thumbnail'
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll'
import { newSeed } from '../../playlists/queue'
import { watchUrl } from '../../videos/paths'
import styles from './PlaylistPanel.module.css'
import type { PlayingList } from './usePlaylistQueue'

/** YouTube's playlist panel on the watch page: the list with the current video marked. */
export default function PlaylistPanel({ queue }: { queue: PlayingList }) {
  const { list, shuffle, videos, position, items } = queue
  const current = position === null ? undefined : videos[position].id
  const [, setParams] = useSearchParams()
  const rows = useRef<HTMLOListElement>(null)
  // The panel scrolls itself; the sentinel inside it shows only near the end of its rows.
  // Shuffled, the list is the first page: no more to load.
  const sentinel = useInfiniteScroll<HTMLLIElement>(
    () => void items.fetchNextPage(),
    !shuffle && items.hasNextPage && !items.isFetchingNextPage && !items.isFetchNextPageError,
  )

  // The video plays on; turned on, the shuffle starts with it.
  function toggleShuffle() {
    setParams(
      (params) => {
        const next = new URLSearchParams(params)
        if (shuffle) {
          next.delete('shuffle')
          next.delete('index')
        } else {
          next.set('shuffle', newSeed())
          next.set('index', '1')
        }
        return next
      },
      { replace: true },
    )
  }

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
        <div className={styles.actions}>
          <IconButton
            icon="shuffle"
            label="Shuffle"
            aria-pressed={shuffle !== null}
            className={shuffle ? styles.on : undefined}
            onClick={toggleShuffle}
          />
        </div>
      </div>
      <ol ref={rows} className={styles.rows}>
        {videos.map((video, index) => {
          const playing = video.id === current
          return (
            <li key={video.id}>
              <Link
                to={watchUrl(video.id, { list, shuffle, index: index + 1 })}
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
