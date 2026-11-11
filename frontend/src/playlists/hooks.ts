import {
  type InfiniteData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import type { Page } from '../videos/types'
import {
  createPlaylist,
  deletePlaylist,
  getPlaylist,
  getSaved,
  getWatchLater,
  listChannelPlaylists,
  listItems,
  listMyPlaylists,
  moveInPlaylist,
  setInPlaylist,
  updatePlaylist,
} from './api'
import type { MyPlaylist, PlaylistItem, PlaylistUpdate } from './types'

// A change to any playlist refetches everything under `all`: counts and covers move with it.
export const playlistKeys = {
  all: ['playlists'] as const,
  detail: (id: string) => ['playlists', 'detail', id] as const,
  items: (id: string) => ['playlists', 'items', id] as const,
  mine: (videoId: string | null) => ['playlists', 'mine', videoId] as const,
  watchLater: ['playlists', 'watch-later'] as const,
  saved: (videoId: string) => ['playlists', 'saved', videoId] as const,
  channel: (handle: string) => ['playlists', 'channel', handle] as const,
}

const firstPage = null as string | null

export function usePlaylist(id: string) {
  return useQuery({ queryKey: playlistKeys.detail(id), queryFn: () => getPlaylist(id) })
}

/** Fills the Save button's bookmark. Under `all`: every tick in the Save dialog refreshes it. */
export function useSaved(videoId: string, enabled: boolean) {
  return useQuery({
    queryKey: playlistKeys.saved(videoId),
    queryFn: () => getSaved(videoId),
    enabled,
  })
}

/** Only for a signed-in viewer: a guest has none. */
export function useWatchLater(enabled: boolean) {
  return useQuery({ queryKey: playlistKeys.watchLater, queryFn: getWatchLater, enabled })
}

export function usePlaylistItems(id: string) {
  return useInfiniteQuery({
    queryKey: playlistKeys.items(id),
    queryFn: ({ pageParam }) => listItems(id, pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
  })
}

export function useChannelPlaylists(handle: string) {
  return useInfiniteQuery({
    queryKey: playlistKeys.channel(handle),
    queryFn: ({ pageParam }) => listChannelPlaylists(handle, pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
  })
}

/** The viewer's playlists; with a video, each one says whether it holds it. */
export function useMyPlaylists(videoId: string | null, enabled = true) {
  return useInfiniteQuery({
    queryKey: playlistKeys.mine(videoId),
    queryFn: ({ pageParam }) => listMyPlaylists(videoId, pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
    enabled,
  })
}

export function useCreatePlaylist() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createPlaylist,
    onSettled: () => queryClient.invalidateQueries({ queryKey: playlistKeys.all }),
  })
}

/** A checkbox of the Save dialog: shows at once, rolls back if the request fails. */
export function useSetInPlaylist(videoId: string) {
  const queryClient = useQueryClient()
  const key = playlistKeys.mine(videoId)
  type Mine = InfiniteData<Page<MyPlaylist>>

  return useMutation({
    mutationFn: ({ playlistId, saved }: { playlistId: string; saved: boolean }) =>
      setInPlaylist(playlistId, videoId, saved),
    onMutate: async ({ playlistId, saved }) => {
      await queryClient.cancelQueries({ queryKey: key })
      const previous = queryClient.getQueryData<Mine>(key)
      if (previous) {
        queryClient.setQueryData<Mine>(key, {
          ...previous,
          pages: previous.pages.map((page) => ({
            ...page,
            items: page.items.map((playlist) =>
              playlist.id === playlistId ? { ...playlist, contains_video: saved } : playlist,
            ),
          })),
        })
      }
      return { previous }
    },
    onError: (_error, _change, context) => {
      if (context?.previous) queryClient.setQueryData(key, context.previous)
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: playlistKeys.all }),
  })
}

export function useUpdatePlaylist(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (changes: PlaylistUpdate) => updatePlaylist(id, changes),
    onSuccess: (playlist) => queryClient.setQueryData(playlistKeys.detail(id), playlist),
    onSettled: () => queryClient.invalidateQueries({ queryKey: playlistKeys.all }),
  })
}

export function useDeletePlaylist() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deletePlaylist,
    onSuccess: (_nothing, id) => {
      queryClient.removeQueries({ queryKey: playlistKeys.detail(id) })
      queryClient.removeQueries({ queryKey: playlistKeys.items(id) })
      // Stale but not refetched now: the page showing the playlist is going away.
      void queryClient.invalidateQueries({ queryKey: playlistKeys.all, refetchType: 'none' })
    },
  })
}

type Items = InfiniteData<Page<PlaylistItem>>

/** The loaded items, changed; `complete`: no page is left to load. */
type ItemsChange<V> = (items: PlaylistItem[], change: V, complete: boolean) => PlaylistItem[]

/** A change to the playlist page's list: shows at once, rolls back if the request fails. */
function useItemsChange<V>(
  playlistId: string,
  request: (change: V) => Promise<void>,
  apply: ItemsChange<V>,
) {
  const queryClient = useQueryClient()
  const key = playlistKeys.items(playlistId)

  return useMutation({
    mutationFn: request,
    onMutate: async (change: V) => {
      await queryClient.cancelQueries({ queryKey: key })
      const previous = queryClient.getQueryData<Items>(key)
      if (previous) {
        const complete = previous.pages.at(-1)?.next_cursor === null
        const items = apply(
          previous.pages.flatMap((page) => page.items),
          change,
          complete,
        )
        queryClient.setQueryData<Items>(key, regroup(previous, items))
      }
      return { previous }
    },
    onError: (_error, _change, context) => {
      if (context?.previous) queryClient.setQueryData(key, context.previous)
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: playlistKeys.all }),
  })
}

/** The items back into pages of the old sizes; the last page takes what is left. */
function regroup(data: Items, items: PlaylistItem[]): Items {
  let start = 0
  const pages = data.pages.map((page, index) => {
    const end = index === data.pages.length - 1 ? items.length : start + page.items.length
    const slice = items.slice(start, end)
    start = end
    return { ...page, items: slice }
  })
  return { ...data, pages }
}

export function useRemoveFromPlaylist(playlistId: string) {
  return useItemsChange<string>(
    playlistId,
    (videoId) => setInPlaylist(playlistId, videoId, false),
    (items, videoId) => items.filter((item) => item.video.id !== videoId),
  )
}

interface Move {
  videoId: string
  /** The video to put it before; null: at the end. */
  before: string | null
}

export function useMoveInPlaylist(playlistId: string) {
  return useItemsChange<Move>(
    playlistId,
    ({ videoId, before }) => moveInPlaylist(playlistId, videoId, before),
    (items, { videoId, before }, complete) => {
      const moving = items.find((item) => item.video.id === videoId)
      if (!moving) return items
      const rest = items.filter((item) => item !== moving)
      // To the end of a list not fully loaded: it goes past the loaded part.
      if (before === null) return complete ? [...rest, moving] : rest
      const at = rest.findIndex((item) => item.video.id === before)
      return at < 0 ? items : [...rest.slice(0, at), moving, ...rest.slice(at)]
    },
  )
}
