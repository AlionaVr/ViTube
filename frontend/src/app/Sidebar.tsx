import { NavLink } from 'react-router'

import { useMe } from '../auth/hooks'
import Icon, { type IconName } from '../components/Icon'
import SignInButton from '../components/SignInButton'
import styles from './Sidebar.module.css'

interface NavItem {
  to: string
  label: string
  icon: IconName
  activeIcon: IconName
}

const MAIN: NavItem[] = [
  { to: '/', label: 'Home', icon: 'home', activeIcon: 'homeFill' },
  {
    to: '/feed/subscriptions',
    label: 'Subscriptions',
    icon: 'subscriptions',
    activeIcon: 'subscriptionsFill',
  },
]
const YOU: NavItem = { to: '/feed/you', label: 'You', icon: 'you', activeIcon: 'youFill' }
const HISTORY: NavItem = {
  to: '/feed/history',
  label: 'History',
  icon: 'history',
  activeIcon: 'history',
}

function NavItems({ items }: { items: NavItem[] }) {
  return items.map((item) => (
    <NavLink
      key={item.to}
      to={item.to}
      end
      className={({ isActive }) => (isActive ? `${styles.item} ${styles.active}` : styles.item)}
    >
      {({ isActive }) => (
        <>
          <Icon name={isActive ? item.activeIcon : item.icon} />
          <span>{item.label}</span>
        </>
      )}
    </NavLink>
  ))
}

export default function Sidebar({ expanded }: { expanded: boolean }) {
  const me = useMe()

  if (!expanded) {
    return (
      <nav id="guide" className={styles.mini} aria-label="Main">
        <NavItems items={[...MAIN, YOU]} />
      </nav>
    )
  }

  return (
    <nav id="guide" className={styles.full} aria-label="Main">
      <section className={styles.section}>
        <NavItems items={MAIN} />
      </section>
      <section className={styles.section}>
        <NavItems items={[YOU, HISTORY]} />
      </section>
      {/* Guests only, as on YouTube. */}
      {me.data === null && (
        <section className={`${styles.section} ${styles.signInPrompt}`}>
          <p>Sign in to like videos, comment, and subscribe.</p>
          <SignInButton />
        </section>
      )}
    </nav>
  )
}
