import IconButton from '../../components/IconButton'
import MenuChoices from '../../components/Menu'
import Popover from '../../components/Popover'
import type { Account } from '../../moderation/api'

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
        <MenuChoices
          choices={[{ icon: 'block', label: `Restrict @${account.handle}`, onSelect: onRestrict }]}
          close={close}
        />
      )}
    </Popover>
  )
}
