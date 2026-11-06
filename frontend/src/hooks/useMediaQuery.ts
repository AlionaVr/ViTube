import { useSyncExternalStore } from 'react'

/** True while the media query matches; re-renders when it flips. */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia(query)
      list.addEventListener('change', onChange)
      return () => list.removeEventListener('change', onChange)
    },
    () => window.matchMedia(query).matches,
  )
}

// YouTube's breakpoints. CSS repeats the numbers in its media queries.
/** The guide can stay open next to the content. */
export const WIDE_SCREEN = '(min-width: 1313px)'
/** The search box folds into an icon. */
export const NARROW_HEADER = '(max-width: 656px)'
