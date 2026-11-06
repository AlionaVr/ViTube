export const SPEEDS = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2]

const VOLUME_KEY = 'vitube:volume'

interface SavedVolume {
  volume: number
  muted: boolean
}

/** The volume carries over to the next video and the next visit, as on YouTube. */
export function loadVolume(): SavedVolume | null {
  try {
    const saved = JSON.parse(localStorage.getItem(VOLUME_KEY) ?? 'null') as SavedVolume | null
    return saved && typeof saved.volume === 'number' ? saved : null
  } catch {
    return null
  }
}

export function saveVolume(volume: SavedVolume): void {
  try {
    localStorage.setItem(VOLUME_KEY, JSON.stringify(volume))
  } catch {
    // Storage blocked: the volume just won't carry over.
  }
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}
