import ErrorState from '../../components/ErrorState'
import Spinner from '../../components/Spinner'
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll'
import { formatUpdated } from '../../lib/format'
import { useMyPlaylists } from '../../playlists/hooks'
import PlaylistCard, { PlaylistCardSkeleton } from '../../playlists/PlaylistCard'
import { VISIBILITY } from '../../playlists/visibility'
import grid from '../../styles/grid.module.css'
import { useViewer } from '../../viewer/useViewer'
import styles from './PlaylistsPage.module.css'
import SignInToSee from './SignInToSee'

const SKELETON_CARDS = 8

function Playlists() {
  const mine = useMyPlaylists(null)
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => void mine.fetchNextPage(),
    mine.hasNextPage && !mine.isFetchingNextPage && !mine.isFetchNextPageError,
  )

  if (mine.isPending) {
    return (
      <div className={grid.feed} aria-busy="true" aria-label="Loading playlists">
        {Array.from({ length: SKELETON_CARDS }, (_, i) => (
          <PlaylistCardSkeleton key={i} />
        ))}
      </div>
    )
  }
  if (!mine.data) {
    return <ErrorState title="Can’t load your playlists" onRetry={() => void mine.refetch()} />
  }
  // Never empty: Watch later is there from sign-up.
  const playlists = mine.data.pages.flatMap((page) => page.items)
  return (
    <>
      <div className={grid.feed}>
        {playlists.map((playlist) => (
          <PlaylistCard
            key={playlist.id}
            playlist={playlist}
            lines={[
              `${VISIBILITY[playlist.visibility].label} • Playlist`,
              formatUpdated(playlist.updated_at),
            ]}
          />
        ))}
      </div>
      <div ref={sentinel} />
      {mine.isFetchingNextPage && (
        <div className={grid.more}>
          <Spinner label="Loading more playlists" />
        </div>
      )}
      {mine.isFetchNextPageError && (
        <ErrorState title="Can’t load more playlists" onRetry={() => void mine.fetchNextPage()} />
      )}
    </>
  )
}

/** /feed/playlists: the viewer's playlists, Watch later first, then the newest. */
export default function PlaylistsPage() {
  const viewer = useViewer()
  return (
    <div className={grid.page}>
      <title>Playlists - ViTube</title>
      {viewer.status === 'guest' ? (
        <SignInToSee
          icon="playlists"
          title="Enjoy your favorite videos"
          text="Sign in to see your playlists"
        />
      ) : (
        viewer.status === 'authenticated' && (
          <>
            <h1 className={styles.title}>Playlists</h1>
            <Playlists />
          </>
        )
      )}
    </div>
  )
}
