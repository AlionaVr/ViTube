import { useSyncExternalStore } from 'react'

/** "device" follows the OS; dark and light pin the theme. */
export type Theme = 'device' | 'dark' | 'light'

/** The inline script in index.html reads it too, before the first paint. */
export const THEME_KEY = 'vitube:theme'

function load(): Theme {
  try {
    const saved = localStorage.getItem(THEME_KEY)
    return saved === 'dark' || saved === 'light' ? saved : 'device'
  } catch {
    return 'device'
  }
}

// tokens.css: no attribute = color-scheme "light dark", the OS decides.
function apply(theme: Theme) {
  if (theme === 'device') delete document.documentElement.dataset.theme
  else document.documentElement.dataset.theme = theme
}

let current = load()
const listeners = new Set<() => void>()

function update(theme: Theme) {
  current = theme
  apply(theme)
  listeners.forEach((listener) => listener())
}

/** Applies at once and keeps the choice in this browser, as YouTube's Appearance setting. */
export function setTheme(theme: Theme): void {
  try {
    if (theme === 'device') localStorage.removeItem(THEME_KEY)
    else localStorage.setItem(THEME_KEY, theme)
  } catch {
    // Storage blocked: the theme lasts until the page closes.
  }
  update(theme)
}

// A choice made in another tab applies here too.
window.addEventListener('storage', (event) => {
  if (event.key === THEME_KEY || event.key === null) update(load())
})

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useTheme(): Theme {
  return useSyncExternalStore(subscribe, () => current)
}
