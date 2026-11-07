import { Link } from 'react-router'

import IconButton from '../components/IconButton'
import Logo from '../components/Logo'
import SignInButton from '../components/SignInButton'
import { useViewer } from '../viewer/useViewer'
import AccountMenu from './AccountMenu'
import styles from './Header.module.css'
import SearchBox from './SearchBox'

interface HeaderProps {
  sidebarExpanded: boolean
  onMenuClick: () => void
}

export default function Header({ sidebarExpanded, onMenuClick }: HeaderProps) {
  const viewer = useViewer()

  return (
    <header className={styles.header}>
      <div className={styles.start}>
        <IconButton
          icon="menu"
          label="Menu"
          aria-expanded={sidebarExpanded}
          aria-controls="guide"
          onClick={onMenuClick}
        />
        <Link to="/" className={styles.logo} aria-label="ViTube home">
          <Logo />
        </Link>
      </div>

      <SearchBox />

      <div className={styles.end}>
        {/* Nothing until /me answers: no "Sign in" flash for signed-in users. */}
        {viewer.status === 'authenticated' ? (
          <AccountMenu user={viewer.user} />
        ) : (
          viewer.status === 'guest' && <SignInButton />
        )}
      </div>
    </header>
  )
}
