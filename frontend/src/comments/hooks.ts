import {
  type InfiniteData,
  type QueryClient,
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query'

import { applyRating, videoKeys } from '../videos/hooks'
import type { Page, Rating, Video } from '../videos/types'
import { addComment, listComments, listReplies, rateComment } from './api'
import type { Comment, CommentSort } from './types'

// Lists and replies share the ['comments', videoId] prefix, so one update reaches all of them.
export const commentKeys = {
  all: (videoId: string) => ['comments', videoId] as const,
  list: (videoId: string, sort: CommentSort) => ['comments', videoId, sort] as const,
  replies: (videoId: string, commentId: string) =>
    ['comments', videoId, 'replies', commentId] as const,
}

type Pages = InfiniteData<Page<Comment>, string | null>

const firstPage = null as string | null

export function useComments(videoId: string, sort: CommentSort) {
  return useInfiniteQuery({
    queryKey: commentKeys.list(videoId, sort),
    queryFn: ({ pageParam }) => listComments(videoId, sort, pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
  })
}

export function useReplies(videoId: string, commentId: string, enabled: boolean) {
  return useInfiniteQuery({
    queryKey: commentKeys.replies(videoId, commentId),
    queryFn: ({ pageParam }) => listReplies(commentId, pageParam),
    initialPageParam: firstPage,
    getNextPageParam: (page) => page.next_cursor,
    enabled,
  })
}

function updateComments(
  queryClient: QueryClient,
  videoId: string,
  update: (comment: Comment) => Comment,
) {
  queryClient.setQueriesData<Pages>(
    { queryKey: commentKeys.all(videoId) },
    (data) =>
      data && {
        ...data,
        pages: data.pages.map((page) => ({ ...page, items: page.items.map(update) })),
      },
  )
}

/** A new comment shows at the top of both sort orders; a reply at the end of its thread. */
export function useAddComment(videoId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ text, parentId }: { text: string; parentId: string | null }) =>
      addComment(videoId, text, parentId),
    onSuccess: (comment, { parentId }) => {
      if (parentId) {
        updateComments(queryClient, videoId, (c) =>
          c.id === parentId ? { ...c, reply_count: c.reply_count + 1 } : c,
        )
        queryClient.setQueryData<Pages>(
          commentKeys.replies(videoId, parentId),
          (data) =>
            data && {
              ...data,
              pages: data.pages.map((page, i) =>
                i === data.pages.length - 1 ? { ...page, items: [...page.items, comment] } : page,
              ),
            },
        )
      } else {
        for (const sort of ['top', 'new'] as const) {
          queryClient.setQueryData<Pages>(
            commentKeys.list(videoId, sort),
            (data) =>
              data && {
                ...data,
                pages: data.pages.map((page, i) =>
                  i === 0 ? { ...page, items: [comment, ...page.items] } : page,
                ),
              },
          )
        }
      }
      queryClient.setQueryData<Video>(
        videoKeys.detail(videoId),
        (video) => video && { ...video, comment_count: video.comment_count + 1 },
      )
    },
  })
}

/** Optimistic like/dislike on a comment or a reply. */
export function useRateComment(videoId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, rating }: { id: string; rating: Rating }) => rateComment(id, rating),
    onMutate: async ({ id, rating }) => {
      await queryClient.cancelQueries({ queryKey: commentKeys.all(videoId) })
      const previous = queryClient.getQueriesData<Pages>({ queryKey: commentKeys.all(videoId) })
      updateComments(queryClient, videoId, (c) => (c.id === id ? applyRating(c, rating) : c))
      return { previous }
    },
    onError: (_error, _vars, context) => {
      for (const [key, data] of context?.previous ?? []) queryClient.setQueryData(key, data)
    },
    onSuccess: (result, { id }) => {
      updateComments(queryClient, videoId, (c) => (c.id === id ? { ...c, ...result } : c))
    },
  })
}
