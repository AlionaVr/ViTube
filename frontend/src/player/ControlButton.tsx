import type { ButtonHTMLAttributes } from 'react'

import Icon, { type IconName } from '../components/Icon'
import styles from './Player.module.css'

interface ControlButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'aria-label'> {
  icon: IconName
  label: string
  /** Shown in the tooltip, as YouTube does: "Pause (k)". */
  shortcut?: string
}

export default function ControlButton({ icon, label, shortcut, ...rest }: ControlButtonProps) {
  return (
    <button
      type="button"
      className={styles.control}
      aria-label={label}
      aria-keyshortcuts={shortcut}
      data-tooltip={shortcut ? `${label} (${shortcut})` : label}
      {...rest}
    >
      <Icon name={icon} size={28} />
    </button>
  )
}
