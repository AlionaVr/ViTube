import type { Account } from '../../moderation/api'
import IconButton from '../../components/IconButton'
import Popover from '../../components/Popover'
import styles from './ModerationPage.module.css'

/** ⋮ on a row, like Studio's options: what admins do about the account behind it. */
export default function RowMenu({
  account,
  onRestrict,
}: {
  account: Account
  onRestrict: () => void
}) {
  return (
    <Popover
      label={`More actions for @${account.handle}`}
      role="menu"
      align="end"
      trigger={(props) => (
        <IconButton icon="moreVert" label={`More actions for @${account.handle}`} {...props} />
      )}
    >
      {(close) => (
        <div className={styles.menu}>
          <button
            type="button"
            role="menuitem"
            className={styles.menuItem}
            onClick={() => {
              close()
              onRestrict()
            }}
          >
            Restrict @{account.handle}
          </button>
        </div>
      )}
    </Popover>
  )
}
