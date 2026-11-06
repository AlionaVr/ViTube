import { vi } from 'vitest'

type Handler = (request: Request) => Response | Promise<Response>

/** Replaces fetch: handlers are keyed by "METHOD /path". Returns the mock to inspect calls. */
export function mockApi(handlers: Record<string, Handler>) {
  const fetch = vi.fn(async (request: Request) => {
    const route = `${request.method} ${new URL(request.url).pathname}`
    const handler = handlers[route]
    if (!handler) throw new Error(`No mock for ${route}`)
    return handler(request)
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

export function json(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export const ANNA = { handle: 'user-k3j9x2m1', email: 'anna@example.com', role: 'user' } as const
