import { useOutletContext } from 'react-router'

import type { User } from '../../api/client'

/** The signed-in moderator, passed by the page around the tabs. */
export function useModerator(): User {
  return useOutletContext<User>()
}
