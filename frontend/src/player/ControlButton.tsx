import type { ButtonHTMLAttributes } from 'react'

import Icon, { type IconName } from '../components/Icon'
import styles from './Player.module.css'

interface ControlButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'aria-label'> {
  icon: IconName
  label: string
  /** Shown in the tooltip, as YouTube does: "Pause (k)". */
  shortcut?: string
  /** Material glyphs fill their box unevenly; sizes are tuned per icon to YouTube's. */
  iconSize?: number
}

export default function ControlButton({
  icon,
  label,
  shortcut,
  iconSize = 28,
  ...rest
}: ControlButtonProps) {
  return (
    <button
      type="button"
      className={styles.control}
      aria-label={label}
      aria-keyshortcuts={shortcut}
      data-tooltip={shortcut ? `${label} (${shortcut})` : label}
      {...rest}
    >
      <Icon name={icon} size={iconSize} />
    </button>
  )
}
