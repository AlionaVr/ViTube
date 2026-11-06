import { useState } from 'react'

const KEY = 'vitube:theater'

/** Theater mode sticks across videos and visits, as on YouTube. */
export function useTheaterMode(): [boolean, () => void] {
  const [theater, setTheater] = useState(() => {
    try {
      return localStorage.getItem(KEY) === '1'
    } catch {
      return false
    }
  })

  function toggle() {
    setTheater((value) => {
      try {
        localStorage.setItem(KEY, value ? '0' : '1')
      } catch {
        // Storage blocked: the choice lasts for this page only.
      }
      return !value
    })
  }

  return [theater, toggle]
}
