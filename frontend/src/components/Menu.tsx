import Icon, { type IconName } from './Icon'
import styles from './Menu.module.css'

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
