import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { ApiError } from '../api/client'
import { pollWhileProcessing } from '../videos/hooks'
import type { OwnVideo } from '../videos/types'
import { createDraft, getUploadLimits, getVideo, type UploadLimits, uploadFile } from './api'
import { formatSize } from './format'

/** The file's trip to the server. After `stored`, the video's status tells the rest. */
export type Transfer =
  | { phase: 'idle' }
  | { phase: 'sending'; progress: number }
  | { phase: 'stored' }
  | { phase: 'failed'; message: string }

export const uploadKeys = {
  limits: ['videos', 'upload-limits'] as const,
  video: (id: string) => ['videos', 'upload', id] as const,
}

/** Rough check before sending: the server checks again, and ffprobe has the last word. */
function looksLikeVideo(file: File): boolean {
  // Some systems give no type for .mkv and the like: let the server decide then.
  return file.type === '' || file.type.startsWith('video/')
}

function titleOf(file: File): string {
  const name = file.name.replace(/\.[^.]+$/, '').trim()
  return name.slice(0, 100) || 'Untitled video'
}

function transferError(error: unknown, limits: UploadLimits | undefined): string {
  if (error instanceof ApiError && error.status === 413 && limits) {
    return `This file is larger than ${formatSize(limits.max_size_bytes)}.`
  }
  // The API's slots or nginx's per-IP limit (HTML, no text of ours): the same advice.
  if (error instanceof ApiError && error.status === 429) {
    return 'Too many uploads at once. Wait for one to finish.'
  }
  if (error instanceof ApiError && error.status !== 0) return error.message
  return 'Upload failed. Check your connection and try again.'
}

export function useUpload() {
  const queryClient = useQueryClient()
  const limits = useQuery({
    queryKey: uploadKeys.limits,
    queryFn: getUploadLimits,
    staleTime: Infinity,
  })
  const [file, setFile] = useState<File | null>(null)
  const [draft, setDraft] = useState<OwnVideo | null>(null)
  const [transfer, setTransfer] = useState<Transfer>({ phase: 'idle' })
  const [pickError, setPickError] = useState<string | null>(null)
  const abort = useRef<AbortController | null>(null)

  // Processing status, while the worker has the video.
  const video = useQuery({
    queryKey: uploadKeys.video(draft?.id ?? ''),
    queryFn: () => getVideo(draft!.id),
    enabled: draft !== null && transfer.phase === 'stored',
    refetchInterval: pollWhileProcessing,
  })

  // Closing the dialog mid-upload stops the request.
  useEffect(() => () => abort.current?.abort(), [])

  async function send(target: OwnVideo, chosen: File) {
    const controller = new AbortController()
    abort.current = controller
    setTransfer({ phase: 'sending', progress: 0 })
    try {
      const stored = await uploadFile(
        target.id,
        chosen,
        (progress) => setTransfer({ phase: 'sending', progress }),
        controller.signal,
      )
      queryClient.setQueryData(uploadKeys.video(stored.id), stored)
      setTransfer({ phase: 'stored' })
    } catch (error) {
      if (controller.signal.aborted) return
      setTransfer({ phase: 'failed', message: transferError(error, limits.data) })
    }
  }

  async function pick(chosen: File) {
    setPickError(null)
    if (!looksLikeVideo(chosen)) {
      setPickError('This file is not a video. Choose a video file.')
      return
    }
    if (limits.data && chosen.size > limits.data.max_size_bytes) {
      setPickError(`This file is larger than ${formatSize(limits.data.max_size_bytes)}.`)
      return
    }
    try {
      const created = await createDraft(titleOf(chosen))
      setFile(chosen)
      setDraft(created)
      await send(created, chosen)
    } catch (error) {
      setPickError(error instanceof ApiError ? error.message : 'Something went wrong. Try again.')
    }
  }

  return {
    limits: limits.data,
    file,
    draft,
    /** The latest server copy: from polling once stored, else the draft. */
    video: video.data ?? draft,
    transfer,
    pickError,
    busy: transfer.phase === 'sending',
    pick,
    /** Sends the same file again after a failed transfer; the draft stays. */
    retry: () => draft && file && send(draft, file),
    cancel: () => abort.current?.abort(),
  }
}
