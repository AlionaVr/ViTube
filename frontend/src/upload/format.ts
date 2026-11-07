import type { UploadLimits } from './api'

const MIB = 1024 * 1024
const GIB = 1024 * MIB

/** Sizes as the server counts them (MiB), in the words people use: "1 GB", "500 MB". */
export function formatSize(bytes: number): string {
  if (bytes >= GIB && bytes % GIB === 0) return `${bytes / GIB} GB`
  return `${Math.round(bytes / MIB)} MB`
}

export function formatLength(seconds: number): string {
  if (seconds % 60 !== 0) return `${seconds} seconds`
  const minutes = seconds / 60
  return minutes === 1 ? '1 minute' : `${minutes} minutes`
}

export function formatLimits(limits: UploadLimits): string {
  return `Up to ${formatSize(limits.max_size_bytes)} and ${formatLength(limits.max_duration_sec)}`
}
