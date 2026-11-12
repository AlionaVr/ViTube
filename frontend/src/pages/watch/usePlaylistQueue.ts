import { useEffect } from 'react'

import { useLiked, useLikedItems } from '../../liked/hooks'
import { LIKED_VIDEOS } from '../../liked/paths'
import { usePlaylist, usePlaylistItems, useWatchLater } from '../../playlists/hooks'
import { type ItemsQuery, videosOf } from '../../playlists/items'
import { parseList, playlistUrl } from '../../playlists/paths'
import { inOrder } from '../../playlists/queue'
import type { Playlist } from '../../playlists/types'
import { watchUrl } from '../../videos/paths'
import type { VideoSummary } from '../../videos/types'
import { useViewer } from '../../viewer/useViewer'

/** Where Next and the end of the video lead: a list's next video, or the list is over. */
export type QueueNext = { status: 'pending' } | { status: 'video'; url: string } | { status: 'end' }

/** A list the watch page plays, as its panel shows it. */
export interface PlayingList {
  /** Its `list=`: LL, WL or a playlist id. */
  list: string
  title: string
  url: string
  owner: Playlist['owner']
  /** How many videos it has: the count until every page is loaded, then the rows. */
  total: number
  videos: VideoSummary[]
  /** The current video's; null while it isn't among the loaded rows. */
  position: number | null
  items: ItemsQuery
  next: QueueNext
}

export type Queue =
  /** No list, or one this viewer can't open: the page plays the video alone. */
  { status: 'none' } | { status: 'loading' } | ({ status: 'ready' } & PlayingList)

/** The list in `list=` around the current video, as YouTube's playlist panel. */
export function usePlaylistQueue(list: string, videoId: string): Queue {
  const ref = parseList(list)
  const kind = ref?.kind
  const viewer = useViewer()
  const signedIn = viewer.status === 'authenticated'

  const watchLater = useWatchLater(signedIn && kind === 'watchLater')
  const playlistId =
    ref?.kind === 'playlist' ? ref.id : kind === 'watchLater' ? watchLater.data?.id : undefined
  const playlist = usePlaylist(playlistId ?? '', kind === 'playlist')
  const playlistItems = usePlaylistItems(playlistId ?? '', playlistId !== undefined)
  const liked = useLiked(signedIn && kind === 'liked')
  const likedItems = useLikedItems(signedIn && kind === 'liked')

  const items: ItemsQuery = kind === 'liked' ? likedItems : playlistItems
  const videos = videosOf(items)
  // A page that fails to load ends the list there: Next falls back to Up next.
  const complete = !items.hasNextPage || items.isFetchNextPageError
  const { position, next } = inOrder(videos, videoId, complete)

  // Pages load until the current video and the one after it are known.
  const { fetchNextPage } = items
  const needsPage = next.status === 'pending' && !items.isFetchingNextPage && !complete
  useEffect(() => {
    if (needsPage) void fetchNextPage()
  }, [needsPage, fetchNextPage])

  if (!ref || (kind !== 'playlist' && viewer.status === 'guest')) return { status: 'none' }
  const stored = kind === 'watchLater' ? watchLater : playlist
  const head =
    kind === 'liked'
      ? liked.data && {
          title: LIKED_VIDEOS.title,
          url: LIKED_VIDEOS.url,
          owner: liked.data.owner,
          count: liked.data.video_count,
        }
      : stored.data && {
          title: stored.data.title,
          url: playlistUrl(stored.data),
          owner: stored.data.owner,
          count: stored.data.video_count,
        }
  const failed = (kind === 'liked' ? liked : stored).isError || (!items.data && !items.isPending)
  if (failed) return { status: 'none' }
  if (!head || !items.data) return { status: 'loading' }

  return {
    status: 'ready',
    list,
    title: head.title,
    url: head.url,
    owner: head.owner,
    total: items.hasNextPage ? head.count : videos.length,
    videos,
    position,
    items,
    next:
      next.status === 'video' ? { status: 'video', url: watchUrl(next.video.id, { list }) } : next,
  }
}
