import type { ReportReason } from './api'

/** YouTube's wording, in YouTube's order. */
export const REASON_LABELS: Record<ReportReason, string> = {
  sexual: 'Sexual content',
  violent: 'Violent or repulsive content',
  hateful: 'Hateful or abusive content',
  harassment: 'Harassment or bullying',
  harmful: 'Harmful or dangerous acts',
  misinformation: 'Misinformation',
  child_abuse: 'Child abuse',
  terrorism: 'Promotes terrorism',
  spam: 'Spam or misleading',
  legal: 'Legal issue',
}

export const REASONS = Object.keys(REASON_LABELS) as ReportReason[]
