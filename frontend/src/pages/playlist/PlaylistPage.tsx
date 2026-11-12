import '@fontsource/roboto/700.css'

import type { InfiniteData, UseInfiniteQueryResult } from '@tanstack/react-query'
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
import { useLiked, useLikedItems } from '../../liked/hooks'
import {
  useMoveInPlaylist,
  usePlaylist,
  usePlaylistItems,
  useRemoveFromPlaylist,
  useWatchLater,
} from '../../playlists/hooks'
import type { Playlist } from '../../playlists/types'
import { VISIBILITY } from '../../playlists/visibility'
import buttons from '../../styles/buttons.module.css'
import { channelUrl, watchUrl } from '../../videos/paths'
import type { Page, VideoSummary } from '../../videos/types'
import { useViewer } from '../../viewer/useViewer'
import SignInToSee from '../feed/SignInToSee'
import { type ItemActions, ItemMenu, PlaylistTools } from './OwnerTools'
import styles from './PlaylistPage.module.css'

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function Missing() {
  return <EmptyState title="The playlist does not exist." />
}

const NOT_CHANGED = 'Couldn’t change the playlist. Try again.'

/** What the header shows: a stored playlist, or Liked videos, which the API counts from likes. */
type Head = Pick<
  Playlist,
  'title' | 'description' | 'visibility' | 'video_count' | 'thumbnail_url' | 'owner'
> & { updated_at: string | null }

function Header({
  playlist,
  first,
  tools,
}: {
  playlist: Head
  first: VideoSummary | undefined
  tools?: ReactNode
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
        {playlist.updated_at && <span>{formatUpdated(playlist.updated_at)}</span>}
      </p>
      {playlist.description && (
        <div className={styles.description}>
          <ClampedText text={playlist.description} lines={2} more="...more" />
        </div>
      )}
      {tools}
      {first && (
        <Link to={watchUrl(first.id)} className={`${buttons.pill} ${styles.playAll}`}>
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

function Row({ video, number, menu }: { video: VideoSummary; number: number; menu?: ReactNode }) {
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

/** A playlist's or Liked videos' pages of rows. */
type ItemsQuery = Pick<
  UseInfiniteQueryResult<InfiniteData<Page<{ video: VideoSummary }>>>,
  | 'data'
  | 'isPending'
  | 'refetch'
  | 'fetchNextPage'
  | 'hasNextPage'
  | 'isFetchingNextPage'
  | 'isFetchNextPageError'
>

function videosOf(query: ItemsQuery): VideoSummary[] {
  return query.data?.pages.flatMap((page) => page.items.map((item) => item.video)) ?? []
}

/** The numbered rows, loaded as the viewer scrolls; `menu` gives a row its ⋮. */
function Items({
  query,
  videos,
  menu,
}: {
  query: ItemsQuery
  videos: VideoSummary[]
  menu?: (index: number) => ReactNode
}) {
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => void query.fetchNextPage(),
    query.hasNextPage && !query.isFetchingNextPage && !query.isFetchNextPageError,
  )
  return (
    <section className={styles.items} aria-label="Videos">
      {query.isPending ? (
        <Spinner label="Loading videos" />
      ) : !query.data ? (
        <ErrorState title="Can’t load the videos" onRetry={() => void query.refetch()} />
      ) : videos.length === 0 ? (
        <p className={styles.empty}>No videos in this playlist yet</p>
      ) : (
        <>
          <ol className={styles.list}>
            {videos.map((video, index) => (
              <Row key={video.id} video={video} number={index + 1} menu={menu?.(index)} />
            ))}
          </ol>
          <div ref={sentinel} />
          {query.isFetchingNextPage && <Spinner label="Loading more videos" />}
          {query.isFetchNextPageError && (
            <ErrorState title="Can’t load more videos" onRetry={() => void query.fetchNextPage()} />
          )}
        </>
      )}
    </section>
  )
}

function PlaylistView({ id }: { id: string }) {
  const playlist = usePlaylist(id)
  const items = usePlaylistItems(id)
  const viewer = useViewer()
  const remove = useRemoveFromPlaylist(id)
  const move = useMoveInPlaylist(id)
  const toast = useToast()

  if (playlist.error instanceof ApiError && playlist.error.status === 404) return <Missing />
  if (playlist.isError) {
    return <ErrorState title="Can’t load this playlist" onRetry={() => void playlist.refetch()} />
  }
  const videos = videosOf(items)
  const own =
    viewer.status === 'authenticated' && playlist.data?.owner.handle === viewer.user.handle

  // Promises, not mutate callbacks: those skip all but the last call, and a removed row unmounts.
  function actionsFor(index: number, title: string): ItemActions {
    const videoId = videos[index].id
    const failed = () => toast(NOT_CHANGED)
    const moveBefore = (before: string | null) =>
      void move.mutateAsync({ videoId, before }).catch(failed)
    return {
      remove: () =>
        void remove.mutateAsync(videoId).then(() => toast(`Removed from ${title}`), failed),
      moveToTop: index > 0 ? () => moveBefore(videos[0].id) : undefined,
      moveToBottom:
        index < videos.length - 1 || items.hasNextPage ? () => moveBefore(null) : undefined,
    }
  }

  const data = playlist.data
  return (
    <div className={styles.page}>
      <title>{data ? `${data.title} - ViTube` : 'ViTube'}</title>
      {data ? (
        <Header
          playlist={data}
          first={videos[0]}
          // Watch later can't be edited or deleted.
          tools={own && data.kind === 'user' && <PlaylistTools playlist={data} />}
        />
      ) : (
        <HeaderSkeleton />
      )}
      <Items
        query={items}
        videos={videos}
        menu={
          own && data
            ? (index) => <ItemMenu title={data.title} actions={actionsFor(index, data.title)} />
            : undefined
        }
      />
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

const LIKED_VIDEOS = 'Liked videos'

function LikedView() {
  const liked = useLiked(true)
  const items = useLikedItems(true)

  if (liked.isError) {
    return <ErrorState title="Can’t load Liked videos" onRetry={() => void liked.refetch()} />
  }
  const videos = videosOf(items)
  return (
    <div className={styles.page}>
      <title>{`${LIKED_VIDEOS} - ViTube`}</title>
      {liked.data ? (
        <Header
          // Private and without a description, as YouTube's.
          playlist={{ ...liked.data, title: LIKED_VIDEOS, description: '', visibility: 'private' }}
          first={videos[0]}
        />
      ) : (
        <HeaderSkeleton />
      )}
      <Items query={items} videos={videos} />
    </div>
  )
}

/** list=LL is the viewer's own Liked videos, as on YouTube: the list of their likes. */
function LikedVideos() {
  const viewer = useViewer()
  if (viewer.status === 'guest') {
    return (
      <SignInToSee
        icon="like"
        title="Enjoy your favorite videos"
        text="Sign in to see the videos you liked"
      />
    )
  }
  if (viewer.status === 'loading') return <Spinner label="Loading Liked videos" />
  return <LikedView />
}

/** /playlist?list=<id>, as on YouTube. */
export default function PlaylistPage() {
  const [params] = useSearchParams()
  const id = params.get('list') ?? ''
  if (id === 'WL') return <WatchLater />
  if (id === 'LL') return <LikedVideos />
  if (!UUID.test(id)) return <Missing />
  return <PlaylistView key={id} id={id} />
}
