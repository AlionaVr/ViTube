import { type ReactNode, useState } from 'react'

import Icon from '../components/Icon'
import IconButton from '../components/IconButton'
import { setTheme, type Theme, useTheme } from '../theme/theme'
import menu from './headerMenu.module.css'
import styles from './MenuPages.module.css'

const CURRENT: Record<Theme, string> = { device: 'Device theme', dark: 'Dark', light: 'Light' }

const CHOICES: { theme: Theme; label: string }[] = [
  { theme: 'device', label: 'Use device theme' },
  { theme: 'dark', label: 'Dark theme' },
  { theme: 'light', label: 'Light theme' },
]

/**
 * A header menu's pages, as on YouTube: the main one (the children, then Appearance in its own group)
 * and the Appearance page it opens in place.
 */
export default function MenuPages({ children }: { children?: ReactNode }) {
  const theme = useTheme()
  // "back" is the main page again, with the focus on the item that opened Appearance.
  const [page, setPage] = useState<'main' | 'appearance' | 'back'>('main')

  if (page === 'appearance') {
    return (
      <>
        <div className={styles.title}>
          <IconButton icon="arrowBack" label="Back" autoFocus onClick={() => setPage('back')} />
          Appearance
        </div>
        <p className={styles.note}>Setting applies to this browser only</p>
        {CHOICES.map((choice) => (
          <button
            key={choice.theme}
            type="button"
            className={menu.item}
            aria-pressed={choice.theme === theme}
            onClick={() => setTheme(choice.theme)}
          >
            <span className={styles.check}>{choice.theme === theme && <Icon name="check" />}</span>
            {choice.label}
          </button>
        ))}
      </>
    )
  }

  return (
    <>
      {children}
      {children && <hr className={menu.divider} />}
      <button
        type="button"
        className={menu.item}
        autoFocus={page === 'back'}
        onClick={() => setPage('appearance')}
      >
        <Icon name="appearance" />
        <span className={styles.label}>Appearance: {CURRENT[theme]}</span>
        <Icon name="chevronRight" />
      </button>
    </>
  )
}
