import '@testing-library/jest-dom/vitest'

import {cleanup} from '@testing-library/react'
import {afterEach} from 'vitest'

// Vitest globals are off, so Testing Library can't register this itself.
afterEach(cleanup)

// jsdom has no matchMedia. Default to a wide screen; tests can spy on it to change that.
window.matchMedia = (query: string) =>
    ({
        media: query,
        matches: true,
        addEventListener() {
        },
        removeEventListener() {
        },
    }) as unknown as MediaQueryList
