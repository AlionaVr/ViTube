// jsdom has no IntersectionObserver or ResizeObserver.

const observers = new Set<MockIntersectionObserver>()

export class MockIntersectionObserver {
  private readonly elements = new Set<Element>()
  private readonly callback: IntersectionObserverCallback

  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback
  }

  observe(element: Element) {
    this.elements.add(element)
    observers.add(this)
  }

  unobserve(element: Element) {
    this.elements.delete(element)
  }

  disconnect() {
    observers.delete(this)
  }

  takeRecords() {
    return []
  }

  fire() {
    const entries = [...this.elements].map((target) => ({ target, isIntersecting: true }))
    this.callback(entries as IntersectionObserverEntry[], this as unknown as IntersectionObserver)
  }
}

/** Pretend everything observed has scrolled into view. Wrap in act(). */
export function intersectAll() {
  for (const observer of [...observers]) observer.fire()
}

export class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
