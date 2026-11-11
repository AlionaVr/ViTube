import type { IconName } from '../components/Icon'
import { VISIBILITY_LABELS } from '../videos/visibility'
import type { Visibility } from './types'

/** Each visibility with YouTube's name for it (the same as for videos) and its mark. */
export const VISIBILITY: Record<Visibility, { label: string; icon: IconName }> = {
  private: { label: VISIBILITY_LABELS.private, icon: 'lock' },
  unlisted: { label: VISIBILITY_LABELS.unlisted, icon: 'link' },
  public: { label: VISIBILITY_LABELS.public, icon: 'public' },
}
