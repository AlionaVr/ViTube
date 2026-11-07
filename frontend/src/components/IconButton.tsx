import type { ButtonHTMLAttributes } from 'react'

import Icon, { type IconName } from './Icon'
import styles from './IconButton.module.css'

interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'aria-label'> {
  icon: IconName
  /** Also the tooltip. */
  label: string
}

/** YouTube's round 40px icon button with a hover circle. */
export default function IconButton({ icon, label, className, ...rest }: IconButtonProps) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={className ? `${styles.button} ${className}` : styles.button}
      {...rest}
    >
      <Icon name={icon} />
    </button>
  )
}
