// Upload API: a draft first, then the file as the raw request body (ADR 0006).
import { ApiError, api, messageOf, readCookie, unwrap } from '../api/client'
import type { components } from '../api/schema'

export type OwnVideo = components['schemas']['VideoOut']
export type UploadLimits = components['schemas']['UploadLimits']
export type VideoChanges = components['schemas']['VideoUpdate']
export type Visibility = components['schemas']['Visibility']
export type VideoStatus = components['schemas']['VideoStatus']

export function getUploadLimits(): Promise<UploadLimits> {
  return unwrap(api.GET('/api/videos/upload-limits'))
}

/** A private draft; the details form may change it later. */
export function createDraft(title: string): Promise<OwnVideo> {
  // Generated types make fields with defaults required, so the defaults are spelled out.
  return unwrap(
    api.POST('/api/videos', { body: { title, description: '', visibility: 'private' } }),
  )
}

export function getVideo(id: string): Promise<OwnVideo> {
  return unwrap(api.GET('/api/videos/{public_id}', { params: { path: { public_id: id } } }))
}

export function updateVideo(id: string, changes: VideoChanges): Promise<OwnVideo> {
  return unwrap(
    api.PATCH('/api/videos/{public_id}', { params: { path: { public_id: id } }, body: changes }),
  )
}

/**
 * Sends the file. XMLHttpRequest, not fetch: only it reports upload progress.
 * Rejects with ApiError, or with an AbortError when `signal` fires.
 */
export function uploadFile(
  id: string,
  file: File,
  onProgress: (fraction: number) => void,
  signal: AbortSignal,
): Promise<OwnVideo> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', `/api/videos/${encodeURIComponent(id)}/file`)
    xhr.responseType = 'json'
    // ADR 0005: unsafe requests echo the CSRF cookie; the browser adds Origin.
    const token = readCookie('csrf_token')
    if (token) xhr.setRequestHeader('X-CSRF-Token', token)
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total)
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(xhr.response as OwnVideo)
      // nginx answers 413 with HTML: no message of ours then.
      else reject(new ApiError(xhr.status, messageOf(xhr.response) ?? xhr.statusText))
    }
    xhr.onerror = () => reject(new ApiError(0, 'Network error'))
    xhr.onabort = () => reject(new DOMException('Upload cancelled', 'AbortError'))
    signal.addEventListener('abort', () => xhr.abort(), { once: true })
    xhr.send(file)
  })
}
