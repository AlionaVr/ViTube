import { useState } from 'react'

/** A UI choice that survives reloads (theater mode, a collapsed guide), as on YouTube. */
export function useStoredFlag(key: string, initial: boolean): [boolean, () => void] {
  const [value, setValue] = useState(() => {
    try {
      const stored = localStorage.getItem(key)
      return stored === null ? initial : stored === '1'
    } catch {
      return initial
    }
  })

  function toggle() {
    setValue((current) => {
      try {
        localStorage.setItem(key, current ? '0' : '1')
      } catch {
        // Storage blocked: the choice lasts for this page only.
      }
      return !current
    })
  }

  return [value, toggle]
}
