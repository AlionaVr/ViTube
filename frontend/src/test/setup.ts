// First: React DOM must find AnimationEvent when it loads.
import './animationEvent'
import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

import { installMediaStubs } from './media'
import { MockIntersectionObserver, MockResizeObserver } from './observers'
import { matchMediaFor } from './screen'

// Vitest globals are off, so Testing Library can't register this itself.
afterEach(cleanup)

// jsdom has no matchMedia. Default to a wide screen; tests call setScreenWidth() to change that.
window.matchMedia = matchMediaFor(1440)

installMediaStubs()

window.IntersectionObserver = MockIntersectionObserver as unknown as typeof IntersectionObserver
window.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver

// jsdom has no <dialog> methods. Enough for tests: toggle `open` and fire `close`.
HTMLDialogElement.prototype.showModal = function () {
  this.open = true
}
HTMLDialogElement.prototype.close = function () {
  this.open = false
  this.dispatchEvent(new Event('close'))
}
