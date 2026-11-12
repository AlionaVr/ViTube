import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import indexHtml from '../../index.html?raw'
import themeInit from '../../public/theme-init.js?raw'
import { setTheme, THEME_KEY, useTheme } from './theme'

const root = document.documentElement

afterEach(() => {
  vi.restoreAllMocks()
  setTheme('device')
  localStorage.clear()
})

describe('theme', () => {
  it('follows the device until a theme is picked', () => {
    const { result } = renderHook(() => useTheme())

    expect(result.current).toBe('device')
    expect(root.dataset.theme).toBeUndefined()
  })

  it('applies a picked theme at once and keeps it in this browser', () => {
    const { result } = renderHook(() => useTheme())

    act(() => setTheme('dark'))

    expect(result.current).toBe('dark')
    expect(root.dataset.theme).toBe('dark')
    expect(localStorage.getItem(THEME_KEY)).toBe('dark')

    act(() => setTheme('device'))

    expect(root.dataset.theme).toBeUndefined()
    expect(localStorage.getItem(THEME_KEY)).toBeNull()
  })

  it('still applies the theme when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })
    const { result } = renderHook(() => useTheme())

    act(() => setTheme('light'))

    expect(result.current).toBe('light')
    expect(root.dataset.theme).toBe('light')
  })

  it('takes a theme picked in another tab', () => {
    const { result } = renderHook(() => useTheme())

    act(() => {
      localStorage.setItem(THEME_KEY, 'dark')
      window.dispatchEvent(new StorageEvent('storage', { key: THEME_KEY, newValue: 'dark' }))
    })

    expect(result.current).toBe('dark')
    expect(root.dataset.theme).toBe('dark')
  })

  it('is set by theme-init.js, which index.html loads before the first paint', () => {
    const head = /<head>([\s\S]*?)<\/head>/.exec(indexHtml)?.[1]
    localStorage.setItem(THEME_KEY, 'dark')

    new Function(themeInit)()

    expect(head).toContain('<script src="/theme-init.js"></script>')
    expect(root.dataset.theme).toBe('dark')
  })
})
