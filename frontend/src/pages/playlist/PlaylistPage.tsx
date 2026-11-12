import '@fontsource/roboto/700.css'

import type { ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router'

import { ApiError } from '../../api/client'
import Avatar from '../../components/Avatar'
import ClampedText from '../../components/ClampedText'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Icon from '../../components/Icon'
import Spinner from '../../components/Spinner'
import Thumbnail from '../../components/Thumbnail'
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll'
import { useToast } from '../../hooks/useToast'
import { formatTimeAgo, formatUpdated, formatVideoCount, formatViews } from '../../lib/format'
import {
  useMoveInPlaylist,
  usePlaylist,
  usePlaylistItems,
  useRemoveFromPlaylist,
  useWatchLater,
} from '../../playlists/hooks'
import type { Playlist, PlaylistItem } from '../../playlists/types'
import { VISIBILITY } from '../../playlists/visibility'
import buttons from '../../styles/buttons.module.css'
import { channelUrl, watchUrl } from '../../videos/paths'
import { useViewer } from '../../viewer/useViewer'
import SignInToSee from '../feed/SignInToSee'
import { type ItemActions, ItemMenu, PlaylistTools } from './OwnerTools'
import styles from './PlaylistPage.module.css'

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function Missing() {
  return <EmptyState title="The playlist does not exist." />
}

const NOT_CHANGED = 'Couldn’t change the playlist. Try again.'

function Header({
  playlist,
  first,
  own,
}: {
  playlist: Playlist
  first: PlaylistItem | undefined
  own: boolean
}) {
  const { label, icon } = VISIBILITY[playlist.visibility]
  const { owner } = playlist
  return (
    <header className={styles.header}>
      {/* The cover, blurred, colors the panel as YouTube's sampled gradient does. */}
      {playlist.thumbnail_url && (
        <div className={styles.backdrop}>
          <img src={playlist.thumbnail_url} alt="" />
        </div>
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
        <span>{formatUpdated(playlist.updated_at)}</span>
      </p>
      {playlist.description && (
        <div className={styles.description}>
          <ClampedText text={playlist.description} lines={2} more="...more" />
        </div>
      )}
      {/* Watch later can't be edited or deleted. */}
      {own && playlist.kind === 'user' && <PlaylistTools playlist={playlist} />}
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

function Row({ item, number, menu }: { item: PlaylistItem; number: number; menu?: ReactNode }) {
  const { video } = item
  return (
    <li className={styles.item}>
      <span className={styles.number}>{number}</span>
      <Link to={watchUrl(video.id)} className={styles.row}>
        <div className={styles.thumbnail}>
          <Thumbnail
            src={video.thumbnail_url}
            durationSec={video.duration_sec}
            videoId={video.id}
            compact
          />
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
      {menu && <div className={styles.menu}>{menu}</div>}
    </li>
  )
}

function PlaylistView({ id }: { id: string }) {
  const playlist = usePlaylist(id)
  const items = usePlaylistItems(id)
  const viewer = useViewer()
  const remove = useRemoveFromPlaylist(id)
  const move = useMoveInPlaylist(id)
  const toast = useToast()
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => void items.fetchNextPage(),
    items.hasNextPage && !items.isFetchingNextPage && !items.isFetchNextPageError,
  )

  if (playlist.error instanceof ApiError && playlist.error.status === 404) return <Missing />
  if (playlist.isError) {
    return <ErrorState title="Can’t load this playlist" onRetry={() => void playlist.refetch()} />
  }
  const videos = items.data?.pages.flatMap((page) => page.items) ?? []
  const own =
    viewer.status === 'authenticated' && playlist.data?.owner.handle === viewer.user.handle

  // Promises, not mutate callbacks: those skip all but the last call, and a removed row unmounts.
  function actionsFor(index: number, title: string): ItemActions {
    const videoId = videos[index].video.id
    const failed = () => toast(NOT_CHANGED)
    const moveBefore = (before: string | null) =>
      void move.mutateAsync({ videoId, before }).catch(failed)
    return {
      remove: () =>
        void remove.mutateAsync(videoId).then(() => toast(`Removed from ${title}`), failed),
      moveToTop: index > 0 ? () => moveBefore(videos[0].video.id) : undefined,
      moveToBottom:
        index < videos.length - 1 || items.hasNextPage ? () => moveBefore(null) : undefined,
    }
  }

  return (
    <div className={styles.page}>
      <title>{playlist.data ? `${playlist.data.title} - ViTube` : 'ViTube'}</title>
      {playlist.data ? (
        <Header playlist={playlist.data} first={videos[0]} own={own} />
      ) : (
        <HeaderSkeleton />
      )}
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
                <Row
                  key={item.video.id}
                  item={item}
                  number={index + 1}
                  menu={
                    own &&
                    playlist.data && (
                      <ItemMenu
                        playlist={playlist.data}
                        actions={actionsFor(index, playlist.data.title)}
                      />
                    )
                  }
                />
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
