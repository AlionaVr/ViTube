import { useEffect, useRef, useState } from 'react'

/**
 * A row that scrolls sideways with YouTube's arrows instead of a scrollbar: whether it has more on
 * each side, and a step of most of its width. `content` changes when the items do, which moves
 * the ends without resizing the row.
 */
export function useScrollArrows<T extends HTMLElement>(content: unknown) {
  const row = useRef<T>(null)
  const [canScroll, setCanScroll] = useState({ left: false, right: false })

  useEffect(() => {
    const element = row.current
    if (!element) return
    const update = () =>
      setCanScroll({
        left: element.scrollLeft > 0,
        right: element.scrollLeft + element.clientWidth < element.scrollWidth - 1,
      })
    // Fires once right away, then on every resize (the guide opening changes the width).
    const observer = new ResizeObserver(update)
    observer.observe(element)
    element.addEventListener('scroll', update, { passive: true })
    return () => {
      observer.disconnect()
      element.removeEventListener('scroll', update)
    }
  }, [content])

  const scrollBy = (direction: -1 | 1) =>
    row.current?.scrollBy({
      left: direction * row.current.clientWidth * 0.8,
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
    })

  return { row, canScroll, scrollBy }
}
