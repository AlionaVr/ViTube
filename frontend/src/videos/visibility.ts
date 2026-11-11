import type { Visibility } from './types'

/** YouTube's names for who may watch a video. */
export const VISIBILITY_LABELS: Record<Visibility, string> = {
  private: 'Private',
  unlisted: 'Unlisted',
  public: 'Public',
}
