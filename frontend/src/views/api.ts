// Views API (ADR 0011): the player reports playback; the server decides what counts.
import { api, unwrap } from '../api/client'

const video = (id: string) => ({ params: { path: { public_id: id } } })

/** Playback began. */
export async function startView(id: string): Promise<void> {
  await unwrap(api.POST('/api/videos/{public_id}/views/start', video(id)))
}

/** Playback reached the threshold. The server counts it once per viewer a day. */
export async function countView(id: string): Promise<void> {
  await unwrap(api.POST('/api/videos/{public_id}/views', video(id)))
}
