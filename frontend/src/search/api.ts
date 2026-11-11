// Search API (see videos/api.ts).
import { api, unwrap } from '../api/client'
import type { components } from '../api/schema'
import type { Page } from '../videos/types'

/** A video in the results, with the start of its description. */
export type SearchResult = components['schemas']['SearchResult']

/** Public videos, best match first. */
export function search(query: string, cursor: string | null): Promise<Page<SearchResult>> {
  return unwrap(api.GET('/api/search', { params: { query: { q: query, cursor } } }))
}

/** Titles of public videos close to what is typed, closest first. */
export function suggest(typed: string): Promise<string[]> {
  return unwrap(api.GET('/api/search/suggestions', { params: { query: { q: typed } } }))
}
