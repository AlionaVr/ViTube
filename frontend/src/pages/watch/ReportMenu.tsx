import { useState } from 'react'

import Icon, { type IconName } from '../../components/Icon'
import IconButton from '../../components/IconButton'
import Popover, { type TriggerProps } from '../../components/Popover'
import SignInGate from '../../components/SignInGate'
import { useMediaQuery } from '../../hooks/useMediaQuery'
import type { ReportTarget } from '../../moderation/api'
import { useViewer } from '../../viewer/useViewer'
import { TWO_COLUMNS } from './layout'
import ReportDialog from './ReportDialog'
import styles from './ReportMenu.module.css'

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
            <div className={styles.menu}>
              <button
                type="button"
                role="menuitem"
                className={styles.item}
                onClick={() => {
                  close()
                  setReporting(true)
                }}
              >
                <Icon name="flag" />
                Report
              </button>
            </div>
          )}
        </Popover>
      )}
      <ReportDialog target={target} open={reporting} onClose={() => setReporting(false)} />
    </>
  )
}
