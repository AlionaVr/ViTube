import createClient, { type Middleware } from 'openapi-fetch'

import type { components, paths } from './schema'

export type User = components['schemas']['UserOut']
export type Credentials = components['schemas']['Credentials']

/** A non-2xx answer. `message` is the server's own text, fit to show to the user. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

export function readCookie(name: string): string | undefined {
  const prefix = `${name}=`
  return document.cookie
    .split('; ')
    .find((cookie) => cookie.startsWith(prefix))
    ?.slice(prefix.length)
}

// ADR 0005: unsafe requests echo the CSRF cookie in a header. The browser adds Origin itself.
const csrf: Middleware = {
  onRequest({ request }) {
    const token = readCookie('csrf_token')
    if (token && !SAFE_METHODS.has(request.method)) {
      request.headers.set('X-CSRF-Token', token)
    }
    return request
  },
}

export const api = createClient<paths>({
  baseUrl: window.location.origin,
  fetch: (request) => fetch(request), // looked up on each call, so tests can replace it
})
api.use(csrf)

interface Answer<T> {
  data?: T
  error?: unknown
  response: Response
}

/** The data of a 2xx answer. Any other answer throws ApiError. */
export async function unwrap<T>(answer: Promise<Answer<T>>): Promise<T> {
  const { data, error, response } = await answer
  if (!response.ok) {
    throw new ApiError(response.status, messageOf(error) ?? response.statusText)
  }
  return data as T
}

export function messageOf(error: unknown): string | undefined {
  // Our errors: {"detail": "..."}. FastAPI's input errors: {"detail": [{"msg": "..."}]}.
  if (typeof error !== 'object' || error === null || !('detail' in error)) return undefined
  const { detail } = error
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && typeof detail[0]?.msg === 'string') return detail[0].msg
  return undefined
}
