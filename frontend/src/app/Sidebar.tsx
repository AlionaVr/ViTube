import { Link, useLocation } from 'react-router'

import { useSubscriptions } from '../channels/hooks'
import Avatar from '../components/Avatar'
import Icon, { type IconName } from '../components/Icon'
import SignInButton from '../components/SignInButton'
import { useSetDemoGuest, useViewer } from '../viewer/useViewer'
import styles from './Sidebar.module.css'

interface NavItem {
  to: string
  label: string
  icon: IconName
  activeIcon?: IconName
}

const HOME: NavItem = { to: '/', label: 'Home', icon: 'home', activeIcon: 'homeFill' }
const SUBSCRIPTIONS: NavItem = {
  to: '/feed/subscriptions',
  label: 'Subscriptions',
  icon: 'subscriptions',
  activeIcon: 'subscriptionsFill',
}
const YOU: NavItem = { to: '/feed/you', label: 'You', icon: 'you', activeIcon: 'youFill' }
const HISTORY: NavItem = { to: '/feed/history', label: 'History', icon: 'history' }

function library(handle: string): NavItem[] {
  return [
    HISTORY,
    { to: '/feed/playlists', label: 'Playlists', icon: 'playlists' },
    { to: `/@${handle}/videos`, label: 'Your videos', icon: 'yourVideos' },
    { to: '/playlist?list=WL', label: 'Watch later', icon: 'watchLater' },
    { to: '/playlist?list=LL', label: 'Liked videos', icon: 'like', activeIcon: 'likeFill' },
  ]
}

interface NavProps {
  /** The drawer closes itself when a link is followed. */
  onNavigate?: () => void
}

function NavItems({ items, onNavigate }: NavProps & { items: NavItem[] }) {
  const { pathname, search } = useLocation()
  return items.map((item) => {
    // Compare the query too: Watch later and Liked videos share a path.
    const active = item.to === pathname + search
    return (
      <Link
        key={item.to}
        to={item.to}
        onClick={onNavigate}
        className={active ? `${styles.item} ${styles.active}` : styles.item}
        aria-current={active ? 'page' : undefined}
      >
        <Icon name={active ? (item.activeIcon ?? item.icon) : item.icon} />
        <span className={styles.label}>{item.label}</span>
      </Link>
    )
  })
}

function SubscriptionList({ onNavigate }: NavProps) {
  const { data: channels } = useSubscriptions()
  if (!channels?.length) return null
  return (
    <section className={styles.section}>
      <h2 className={styles.title}>Subscriptions</h2>
      {channels.map((channel) => (
        <Link
          key={channel.handle}
          to={`/@${channel.handle}`}
          onClick={onNavigate}
          className={styles.item}
        >
          <Avatar name={channel.name} src={channel.avatar_url} size={24} />
          <span className={styles.label}>{channel.name}</span>
        </Link>
      ))}
    </section>
  )
}

// Dev only: check the signed-in and guest UI without the auth backend.
function DemoViewerSwitch() {
  const viewer = useViewer()
  const setGuest = useSetDemoGuest()
  if (viewer.status === 'loading') return null
  const guest = viewer.status === 'guest'
  return (
    <p>
      Demo: {guest ? 'guest' : `@${viewer.user.handle}`}.{' '}
      <button type="button" className={styles.footerButton} onClick={() => setGuest(!guest)}>
        {guest ? 'Sign in as the demo user' : 'View as a guest'}
      </button>
    </p>
  )
}

/** The full guide: in the persistent sidebar and in the drawer. */
export function GuideContent({ onNavigate }: NavProps) {
  const viewer = useViewer()
  return (
    <>
      <section className={styles.section}>
        <NavItems items={[HOME, SUBSCRIPTIONS]} onNavigate={onNavigate} />
      </section>
      {viewer.status === 'authenticated' && (
        <>
          <section className={styles.section}>
            <Link to="/feed/you" onClick={onNavigate} className={`${styles.item} ${styles.you}`}>
              You
              <Icon name="chevronRight" size={20} />
            </Link>
            <NavItems items={library(viewer.user.handle)} onNavigate={onNavigate} />
          </section>
          <SubscriptionList onNavigate={onNavigate} />
        </>
      )}
      {viewer.status === 'guest' && (
        <>
          <section className={styles.section}>
            <NavItems items={[YOU, HISTORY]} onNavigate={onNavigate} />
          </section>
          <section className={`${styles.section} ${styles.signInPrompt}`}>
            <p>Sign in to like videos, comment, and subscribe.</p>
            <SignInButton />
          </section>
        </>
      )}
      <footer className={styles.footer}>
        {import.meta.env.DEV && <DemoViewerSwitch />}
        <p>© {new Date().getFullYear()} ViTube</p>
      </footer>
    </>
  )
}

export function FullGuide() {
  return (
    <nav id="guide" className={styles.full} aria-label="Main">
      <GuideContent />
    </nav>
  )
}

/** `id` only when the menu button toggles this guide (wide screens). */
export function MiniGuide({ id }: { id?: string }) {
  return (
    <nav id={id} className={styles.mini} aria-label="Main">
      <NavItems items={[HOME, SUBSCRIPTIONS, YOU]} />
    </nav>
  )
}
