import IconButton from '../components/IconButton'
import Popover from '../components/Popover'
import MenuPages from './MenuPages'
import styles from './SettingsMenu.module.css'

/** A guest's ⋮ next to Sign in, as on YouTube: the settings that need no account. */
export default function SettingsMenu() {
  return (
    <Popover
      label="Settings"
      align="end"
      trigger={(props) => <IconButton icon="moreVert" label="Settings" {...props} />}
    >
      {() => (
        <div className={styles.pages}>
          <MenuPages />
        </div>
      )}
    </Popover>
  )
}
