import { useEffect, useEffectEvent, useRef } from 'react'

/**
 * Calls `loadMore` when the returned sentinel gets close to the viewport.
 * Re-arms when `enabled` turns back on, so a short page keeps loading until the screen is full.
 */
export function useInfiniteScroll<T extends Element>(loadMore: () => void, enabled: boolean) {
  const sentinel = useRef<T>(null)
  const onVisible = useEffectEvent(loadMore)

  useEffect(() => {
    const element = sentinel.current
    if (!element || !enabled) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) onVisible()
      },
      // Start loading about a screen before the end, as YouTube does.
      { rootMargin: '0px 0px 1000px 0px' },
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [enabled])

  return sentinel
}
