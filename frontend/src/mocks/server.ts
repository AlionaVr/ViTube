// In-memory stand-in for the subscriptions API until Channels & Social has it; only channels/api.ts
// imports it. Answers like the API will: a guest has no subscriptions.
import { fetchMe } from '../auth/hooks'
import type { ChannelSummary } from '../channels/types'

const LATENCY_MS = import.meta.env.MODE === 'test' ? 0 : 400

/** Any signed-in viewer is subscribed to these made-up channels. */
const SUBSCRIPTIONS: ChannelSummary[] = [
  { handle: 'framebyframe', name: 'Frame by Frame', avatar_url: null },
  { handle: 'dragonnotes', name: 'Dragon Notes', avatar_url: null },
  { handle: 'slowbloom', name: 'Slow Bloom', avatar_url: null },
  { handle: 'multrazbor', name: 'Мультразбор', avatar_url: null },
]

/** No auth backend (offline dev): a guest, as in the UI. */
async function signedIn(): Promise<boolean> {
  await new Promise((resolve) => setTimeout(resolve, LATENCY_MS))
  try {
    return (await fetchMe()) !== null
  } catch {
    return false
  }
}

export async function listSubscriptions(): Promise<ChannelSummary[]> {
  return (await signedIn()) ? SUBSCRIPTIONS : []
}
