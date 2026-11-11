import '@fontsource/roboto/700.css'

import { Link, useSearchParams } from 'react-router'

import { ApiError } from '../../api/client'
import Avatar from '../../components/Avatar'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Icon from '../../components/Icon'
import Spinner from '../../components/Spinner'
import Thumbnail from '../../components/Thumbnail'
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll'
import { formatTimeAgo, formatVideoCount, formatViews } from '../../lib/format'
import { usePlaylist, usePlaylistItems, useWatchLater } from '../../playlists/hooks'
import type { Playlist, PlaylistItem } from '../../playlists/types'
import { VISIBILITY } from '../../playlists/visibility'
import buttons from '../../styles/buttons.module.css'
import { channelUrl, watchUrl } from '../../videos/paths'
import { useViewer } from '../../viewer/useViewer'
import SignInToSee from '../feed/SignInToSee'
import styles from './PlaylistPage.module.css'

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function Missing() {
  return <EmptyState title="The playlist does not exist." />
}

function Header({ playlist, first }: { playlist: Playlist; first: PlaylistItem | undefined }) {
  const { label, icon } = VISIBILITY[playlist.visibility]
  const { owner } = playlist
  return (
    <header className={styles.header}>
      {/* The cover, blurred, colors the panel as YouTube's sampled gradient does. */}
      {playlist.thumbnail_url && (
        <img className={styles.backdrop} src={playlist.thumbnail_url} alt="" />
      )}
      <div className={styles.cover}>
        {playlist.thumbnail_url ? (
          <img src={playlist.thumbnail_url} alt="" />
        ) : (
          <Icon name="playlists" size={48} />
        )}
      </div>
      <h1 className={styles.title}>{playlist.title}</h1>
      <Link to={channelUrl(owner.handle)} className={styles.owner}>
        <Avatar name={owner.name} src={owner.avatar_url} size={24} />
        {owner.name}
      </Link>
      <p className={styles.meta}>
        <span>Playlist</span>
        <span className={styles.visibility}>
          <Icon name={icon} size={16} />
          {label}
        </span>
        <span>{formatVideoCount(playlist.video_count)}</span>
        <span>Updated {formatTimeAgo(playlist.updated_at)}</span>
      </p>
      {playlist.description && <p className={styles.description}>{playlist.description}</p>}
      {first && (
        <Link to={watchUrl(first.video.id)} className={`${buttons.pill} ${styles.playAll}`}>
          <Icon name="play" />
          Play all
        </Link>
      )}
    </header>
  )
}

function HeaderSkeleton() {
  return (
    <div
      className={`${styles.header} ${styles.ghostHeader}`}
      aria-busy="true"
      aria-label="Loading playlist"
    >
      <div className={`${styles.cover} ${styles.ghost}`} />
    </div>
  )
}

function Row({ item, number }: { item: PlaylistItem; number: number }) {
  const { video } = item
  return (
    <li className={styles.item}>
      <span className={styles.number}>{number}</span>
      <Link to={watchUrl(video.id)} className={styles.row}>
        <div className={styles.thumbnail}>
          <Thumbnail src={video.thumbnail_url} durationSec={video.duration_sec} compact />
        </div>
        <div className={styles.rowText}>
          <h3 className={styles.rowTitle} title={video.title}>
            {video.title}
          </h3>
          <p className={styles.rowMeta}>
            {video.channel.name} • {formatViews(video.view_count)} •{' '}
            {formatTimeAgo(video.created_at)}
          </p>
        </div>
      </Link>
    </li>
  )
}

function PlaylistView({ id }: { id: string }) {
  const playlist = usePlaylist(id)
  const items = usePlaylistItems(id)
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => void items.fetchNextPage(),
    items.hasNextPage && !items.isFetchingNextPage && !items.isFetchNextPageError,
  )

  if (playlist.error instanceof ApiError && playlist.error.status === 404) return <Missing />
  if (playlist.isError) {
    return <ErrorState title="Can’t load this playlist" onRetry={() => void playlist.refetch()} />
  }
  const videos = items.data?.pages.flatMap((page) => page.items) ?? []
  return (
    <div className={styles.page}>
      <title>{playlist.data ? `${playlist.data.title} - ViTube` : 'ViTube'}</title>
      {playlist.data ? <Header playlist={playlist.data} first={videos[0]} /> : <HeaderSkeleton />}
      <section className={styles.items} aria-label="Videos">
        {items.isPending ? (
          <Spinner label="Loading videos" />
        ) : !items.data ? (
          <ErrorState title="Can’t load the videos" onRetry={() => void items.refetch()} />
        ) : videos.length === 0 ? (
          <p className={styles.empty}>No videos in this playlist yet</p>
        ) : (
          <>
            <ol className={styles.list}>
              {videos.map((item, index) => (
                <Row key={item.video.id} item={item} number={index + 1} />
              ))}
            </ol>
            <div ref={sentinel} />
            {items.isFetchingNextPage && <Spinner label="Loading more videos" />}
            {items.isFetchNextPageError && (
              <ErrorState
                title="Can’t load more videos"
                onRetry={() => void items.fetchNextPage()}
              />
            )}
          </>
        )}
      </section>
    </div>
  )
}

/** list=WL is the viewer's own Watch later, as on YouTube: its id comes from the API. */
function WatchLater() {
  const viewer = useViewer()
  const watchLater = useWatchLater(viewer.status === 'authenticated')

  if (viewer.status === 'guest') {
    return (
      <SignInToSee
        icon="watchLater"
        title="Save videos for later"
        text="Sign in to see the videos you saved to Watch later"
      />
    )
  }
  if (watchLater.data) return <PlaylistView id={watchLater.data.id} />
  if (watchLater.isError) {
    return <ErrorState title="Can’t load Watch later" onRetry={() => void watchLater.refetch()} />
  }
  return <Spinner label="Loading Watch later" />
}

/** /playlist?list=<id>, as on YouTube. */
export default function PlaylistPage() {
  const [params] = useSearchParams()
  const id = params.get('list') ?? ''
  if (id === 'WL') return <WatchLater />
  if (!UUID.test(id)) return <Missing />
  return <PlaylistView key={id} id={id} />
}
