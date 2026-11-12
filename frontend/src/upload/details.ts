import type { Category, OwnVideo, Visibility } from '../videos/types'

/** What the owner edits: in the upload dialog and in Studio's Edit details. */
export interface VideoDetails {
  title: string
  description: string
  category: Category
  visibility: Visibility
}

export function detailsOf(video: OwnVideo): VideoDetails {
  const { title, description, category, visibility } = video
  return { title, description, category, visibility }
}

/** Only the fields that differ: an edit sends what the owner changed, nothing it didn't see. */
export function changedDetails(before: VideoDetails, after: VideoDetails): Partial<VideoDetails> {
  return Object.fromEntries(
    Object.entries(after).filter(([key, value]) => before[key as keyof VideoDetails] !== value),
  )
}
