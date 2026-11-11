import { useOutletContext } from 'react-router'

import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Spinner from '../../components/Spinner'
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll'
import { useChannelPlaylists } from '../../playlists/hooks'
import PlaylistCard, { PlaylistCardSkeleton } from '../../playlists/PlaylistCard'
import grid from '../../styles/grid.module.css'
import styles from './ChannelPlaylists.module.css'

const SKELETON_CARDS = 8

/** The Playlists tab: the channel's public playlists, newest first. */
export default function ChannelPlaylists() {
  const handle = useOutletContext<string>()
  const playlists = useChannelPlaylists(handle)
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => void playlists.fetchNextPage(),
    playlists.hasNextPage && !playlists.isFetchingNextPage && !playlists.isFetchNextPageError,
  )
  const items = playlists.data?.pages.flatMap((page) => page.items) ?? []

  if (playlists.isSuccess && items.length === 0) {
    return <EmptyState title="This channel doesn’t have any playlists" />
  }
  return (
    <div className={`${grid.container} ${styles.tab}`}>
      {playlists.isPending ? (
        <div className={grid.grid} aria-busy="true" aria-label="Loading playlists">
          {Array.from({ length: SKELETON_CARDS }, (_, i) => (
            <PlaylistCardSkeleton key={i} />
          ))}
        </div>
      ) : !playlists.data ? (
        <ErrorState title="Can’t load playlists" onRetry={() => void playlists.refetch()} />
      ) : (
        <>
          <div className={grid.grid}>
            {items.map((playlist) => (
              <PlaylistCard key={playlist.id} playlist={playlist} />
            ))}
          </div>
          <div ref={sentinel} />
          {playlists.isFetchingNextPage && (
            <div className={grid.more}>
              <Spinner label="Loading more playlists" />
            </div>
          )}
          {playlists.isFetchNextPageError && (
            <ErrorState
              title="Can’t load more playlists"
              onRetry={() => void playlists.fetchNextPage()}
            />
          )}
        </>
      )}
    </div>
  )
}
