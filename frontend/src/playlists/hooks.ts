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
  getPlaylist,
  getWatchLater,
  listItems,
  listMyPlaylists,
  setInPlaylist,
} from './api'
import type { MyPlaylist } from './types'

// A change to any playlist refetches everything under `all`: counts and covers move with it.
export const playlistKeys = {
  all: ['playlists'] as const,
  detail: (id: string) => ['playlists', 'detail', id] as const,
  items: (id: string) => ['playlists', 'items', id] as const,
  mine: (videoId: string | null) => ['playlists', 'mine', videoId] as const,
  watchLater: ['playlists', 'watch-later'] as const,
}

const firstPage = null as string | null

export function usePlaylist(id: string) {
  return useQuery({ queryKey: playlistKeys.detail(id), queryFn: () => getPlaylist(id) })
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
