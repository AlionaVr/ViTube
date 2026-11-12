import { formatUpdated } from '../lib/format'
import type { Visibility } from './types'
import { VISIBILITY } from './visibility'

/** A playlist card's lines, as YouTube's: "Private • Playlist", then when it last changed. */
export function playlistLines(visibility: Visibility, updatedAt: string | null): string[] {
  const kind = `${VISIBILITY[visibility].label} • Playlist`
  return updatedAt ? [kind, formatUpdated(updatedAt)] : [kind]
}
