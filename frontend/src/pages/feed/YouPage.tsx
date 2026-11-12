import '@fontsource/roboto/700.css'

import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { User } from '../../api/client'
import Avatar from '../../components/Avatar'
import ErrorState from '../../components/ErrorState'
import VideoCard, { VideoCardSkeleton } from '../../components/VideoCard'
import { useHistory } from '../../history/hooks'
import { NARROW_HEADER, useMediaQuery } from '../../hooks/useMediaQuery'
import { useLiked, useLikedItems } from '../../liked/hooks'
import { LIKED_VIDEOS } from '../../liked/paths'
import { useMyPlaylists, usePlaylistItems, useWatchLater } from '../../playlists/hooks'
import PlaylistCard, { PlaylistCardSkeleton } from '../../playlists/PlaylistCard'
import { playlistUrl } from '../../playlists/paths'
import type { Playlist } from '../../playlists/types'
import buttons from '../../styles/buttons.module.css'
import { channelUrl } from '../../videos/paths'
import type { VideoSummary } from '../../videos/types'
import { useViewer } from '../../viewer/useViewer'
import SignInToSee from './SignInToSee'
import styles from './YouPage.module.css'

const SHELF_SIZE = 12 // a row's worth: View all opens the rest
const SKELETON_CARDS = 4

/** What a shelf's query looks like here: loading, failed or its items. */
interface Loaded<T> {
  items: T[] | undefined
  isError: boolean
  retry: () => void
}

function Shelf<T>({
  title,
  to,
  loaded,
  skeleton,
  children,
}: {
  title: string
  to: string
  loaded: Loaded<T>
  skeleton: ReactNode
  children: (items: T[]) => ReactNode
}) {
  const { items } = loaded
  // Nothing to show yet, nothing to show at all: an empty shelf is left out.
  if (items?.length === 0) return null
  return (
    <section className={styles.shelf} aria-label={title}>
      <div className={styles.shelfTop}>
        <h2 className={styles.shelfTitle}>
          <Link to={to}>{title}</Link>
        </h2>
        <Link to={to} className={`${buttons.pill} ${buttons.small} ${buttons.tonal}`}>
          View all
        </Link>
      </div>
      {loaded.isError ? (
        <ErrorState title={`Can’t load ${title.toLowerCase()}`} onRetry={loaded.retry} />
      ) : (
        <div className={styles.row} aria-busy={!items}>
          {items ? children(items.slice(0, SHELF_SIZE)) : skeleton}
        </div>
      )}
    </section>
  )
}

function videoCards(videos: VideoSummary[]) {
  return videos.map((video) => <VideoCard key={video.id} video={video} />)
}

const videoSkeletons = Array.from({ length: SKELETON_CARDS }, (_, i) => (
  <VideoCardSkeleton key={i} />
))

function HistoryShelf() {
  const history = useHistory('')
  return (
    <Shelf
      title="History"
      to="/feed/history"
      loaded={{
        items: history.data?.pages[0].items.map((item) => item.video),
        isError: history.isError,
        retry: () => void history.refetch(),
      }}
      skeleton={videoSkeletons}
    >
      {videoCards}
    </Shelf>
  )
}

/** A playlist card: a stored playlist, or Liked videos. */
interface Card {
  playlist: Pick<Playlist, 'title' | 'thumbnail_url' | 'video_count'>
  url: string
}

function PlaylistsShelf() {
  const mine = useMyPlaylists(null)
  const liked = useLiked(true)
  // As /feed/playlists: Liked videos, then Watch later and the newest.
  const items: Card[] | undefined =
    mine.data && liked.data
      ? [
          { playlist: { ...liked.data, title: LIKED_VIDEOS.title }, url: LIKED_VIDEOS.url },
          ...mine.data.pages[0].items.map((playlist) => ({ playlist, url: playlistUrl(playlist) })),
        ]
      : undefined
  return (
    <Shelf
      title="Playlists"
      to="/feed/playlists"
      loaded={{
        items,
        isError: mine.isError || liked.isError,
        retry: () => {
          if (mine.isError) void mine.refetch()
          if (liked.isError) void liked.refetch()
        },
      }}
      skeleton={Array.from({ length: SKELETON_CARDS }, (_, i) => (
        <PlaylistCardSkeleton key={i} />
      ))}
    >
      {(playlists) =>
        playlists.map(({ playlist, url }) => (
          <PlaylistCard key={url} playlist={playlist} url={url} />
        ))
      }
    </Shelf>
  )
}

function WatchLaterShelf() {
  const watchLater = useWatchLater(true)
  // Its items are read by the playlist's id.
  const items = usePlaylistItems(watchLater.data?.id ?? '', watchLater.isSuccess)
  return (
    <Shelf
      title="Watch later"
      to="/playlist?list=WL"
      loaded={{
        items: items.data?.pages[0].items.map((item) => item.video),
        isError: watchLater.isError || items.isError,
        retry: () => void (watchLater.isError ? watchLater.refetch() : items.refetch()),
      }}
      skeleton={videoSkeletons}
    >
      {videoCards}
    </Shelf>
  )
}

function LikedShelf() {
  const liked = useLikedItems(true)
  return (
    <Shelf
      title="Liked videos"
      to={LIKED_VIDEOS.url}
      loaded={{
        items: liked.data?.pages[0].items.map((item) => item.video),
        isError: liked.isError,
        retry: () => void liked.refetch(),
      }}
      skeleton={videoSkeletons}
    >
      {videoCards}
    </Shelf>
  )
}

function Header({ user }: { user: User }) {
  const narrow = useMediaQuery(NARROW_HEADER)
  return (
    <header className={styles.header}>
      <Avatar name={user.handle} size={narrow ? 72 : 120} />
      <div className={styles.names}>
        <h1 className={styles.name}>{user.handle}</h1>
        <p className={styles.meta}>
          @{user.handle}
          {' • '}
          <Link to={channelUrl(user.handle)} className={styles.channelLink}>
            View channel
          </Link>
        </p>
      </div>
    </header>
  )
}

/** /feed/you: YouTube's You page. The viewer's channel, then shelves of their own lists. */
export default function YouPage() {
  const viewer = useViewer()
  return (
    <div className={styles.page}>
      <title>You - ViTube</title>
      {viewer.status === 'guest' && (
        <SignInToSee
          icon="you"
          title="Enjoy your favorite videos"
          text="Sign in to access videos that you’ve liked or saved"
        />
      )}
      {viewer.status === 'authenticated' && (
        <>
          <Header user={viewer.user} />
          <HistoryShelf />
          <PlaylistsShelf />
          <WatchLaterShelf />
          <LikedShelf />
        </>
      )}
    </div>
  )
}
