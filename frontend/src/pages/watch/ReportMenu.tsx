import { useState } from 'react'

import { type IconName } from '../../components/Icon'
import IconButton from '../../components/IconButton'
import MenuChoices from '../../components/Menu'
import Popover, { type TriggerProps } from '../../components/Popover'
import SignInGate from '../../components/SignInGate'
import { useMediaQuery } from '../../hooks/useMediaQuery'
import type { ReportTarget } from '../../moderation/api'
import { useViewer } from '../../viewer/useViewer'
import { TWO_COLUMNS } from './layout'
import ReportDialog from './ReportDialog'

interface ReportMenuProps {
  target: ReportTarget
  /** The channel behind it: no one reports their own content. */
  owner: string
  icon: Extract<IconName, 'moreHoriz' | 'moreVert'>
  label: string
  className?: string
}

/** YouTube's ⋯ under a video or ⋮ on a comment, with Report. A guest is asked to sign in. */
export default function ReportMenu({ target, owner, icon, label, className }: ReportMenuProps) {
  const viewer = useViewer()
  const [reporting, setReporting] = useState(false)
  // YouTube opens these to the right, over Up next; in one column that would leave the screen.
  const align = useMediaQuery(TWO_COLUMNS) ? 'start' : 'end'
  const trigger = (props: TriggerProps) => (
    <IconButton icon={icon} label={label} className={className} {...props} />
  )

  if (viewer.status === 'authenticated' && viewer.user.handle === owner) return null
  return (
    <>
      {viewer.status === 'guest' ? (
        <SignInGate
          title={`Need to report the ${target.kind}?`}
          text="Sign in to report inappropriate content."
          align={align}
          onAction={() => setReporting(true)}
        >
          {trigger}
        </SignInGate>
      ) : (
        <Popover
          label={label}
          role="menu"
          align={align}
          trigger={(props) => trigger({ ...props, disabled: viewer.status === 'loading' })}
        >
          {(close) => (
            <MenuChoices
              choices={[{ icon: 'flag', label: 'Report', onSelect: () => setReporting(true) }]}
              close={close}
            />
          )}
        </Popover>
      )}
      <ReportDialog target={target} open={reporting} onClose={() => setReporting(false)} />
    </>
  )
}
