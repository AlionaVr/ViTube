import Icon, { type IconName } from './Icon'
import IconButton from './IconButton'
import styles from './Menu.module.css'
import Popover from './Popover'

export interface MenuChoice {
  icon: IconName
  label: string
  onSelect: () => void
}

/** YouTube's menu lines, icon and label, for a Popover with role="menu". A choice closes it first. */
export default function MenuChoices({
  choices,
  close,
}: {
  choices: MenuChoice[]
  close: () => void
}) {
  return (
    <div className={styles.menu}>
      {choices.map((choice) => (
        <button
          key={choice.label}
          type="button"
          role="menuitem"
          className={styles.choice}
          onClick={() => {
            close()
            choice.onSelect()
          }}
        >
          <Icon name={choice.icon} />
          {choice.label}
        </button>
      ))}
    </div>
  )
}

/** YouTube's ⋮ button and its menu. `className` styles the button. */
export function Menu({
  label,
  choices,
  align = 'end',
  className,
}: {
  label: string
  choices: MenuChoice[]
  align?: 'start' | 'end'
  className?: string
}) {
  return (
    <Popover
      label={label}
      role="menu"
      align={align}
      trigger={(props) => (
        <IconButton icon="moreVert" label={label} className={className} {...props} />
      )}
    >
      {(close) => <MenuChoices choices={choices} close={close} />}
    </Popover>
  )
}
