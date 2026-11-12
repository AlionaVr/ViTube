import { NavLink, Outlet } from 'react-router'

import EmptyState from '../../components/EmptyState'
import SignInButton from '../../components/SignInButton'
import Spinner from '../../components/Spinner'
import { canModerate, isAdmin } from '../../moderation/roles'
import { useViewer } from '../../viewer/useViewer'
import NotFoundPage from '../NotFoundPage'
import styles from './ModerationPage.module.css'

const TABS = [
  { to: '/moderation', label: 'Reports', end: true, adminOnly: false },
  { to: '/moderation/hidden', label: 'Hidden videos', end: false, adminOnly: false },
  { to: '/moderation/accounts', label: 'Accounts', end: false, adminOnly: true },
  { to: '/moderation/audit', label: 'Audit log', end: false, adminOnly: true },
]

/** /moderation: reports from viewers and what moderators do about them (ADR 0009). */
export default function ModerationPage() {
  const viewer = useViewer()
  if (viewer.status === 'loading') {
    return (
      <div className={styles.loading}>
        <Spinner />
      </div>
    )
  }
  if (viewer.status === 'guest') {
    return (
      <EmptyState title="Sign in to review reports">
        <SignInButton />
      </EmptyState>
    )
  }
  // Others don't learn more than about any unknown page; the API refuses them anyway.
  if (!canModerate(viewer.user)) return <NotFoundPage />

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Moderation</h1>
      <nav className={styles.tabs} aria-label="Moderation">
        {TABS.filter((tab) => !tab.adminOnly || isAdmin(viewer.user)).map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.end}
            className={({ isActive }) => (isActive ? `${styles.tab} ${styles.active}` : styles.tab)}
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <Outlet context={viewer.user} />
    </div>
  )
}
