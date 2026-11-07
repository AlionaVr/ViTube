import { vi } from 'vitest'

/** A matchMedia that answers min-width/max-width queries for the given screen width. */
export function matchMediaFor(width: number): typeof window.matchMedia {
  return (query: string) => {
    const min = /min-width:\s*(\d+)px/.exec(query)
    const max = /max-width:\s*(\d+)px/.exec(query)
    const matches =
      (min !== null || max !== null) &&
      (!min || width >= Number(min[1])) &&
      (!max || width <= Number(max[1]))
    return {
      media: query,
      matches,
      addEventListener() {},
      removeEventListener() {},
    } as unknown as MediaQueryList
  }
}

/** Pretend the window is this wide for the rest of the test (restoreMocks undoes it). */
export function setScreenWidth(width: number) {
  vi.spyOn(window, 'matchMedia').mockImplementation(matchMediaFor(width))
}
