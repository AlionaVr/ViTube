import type { IconName } from '../components/Icon'
import type { Visibility } from './types'

/** How YouTube names and marks each visibility. */
export const VISIBILITY: Record<Visibility, { label: string; icon: IconName }> = {
  private: { label: 'Private', icon: 'lock' },
  unlisted: { label: 'Unlisted', icon: 'link' },
  public: { label: 'Public', icon: 'public' },
}
