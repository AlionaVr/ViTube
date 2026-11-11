// Hand-written until the API exists; then replaced by types from schema.d.ts. snake_case as FastAPI sends it.

/** What a card or a comment shows about a channel. */
export interface ChannelSummary {
  handle: string
  name: string
  avatar_url: string | null
}
