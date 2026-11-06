import { Link } from 'react-router'

import IconButton from '../components/IconButton'
import Logo from '../components/Logo'
import SignInButton from '../components/SignInButton'
import styles from './Header.module.css'
import SearchBox from './SearchBox'

interface HeaderProps {
  sidebarExpanded: boolean
  onMenuClick: () => void
}

export default function Header({ sidebarExpanded, onMenuClick }: HeaderProps) {
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
        <SignInButton />
      </div>
    </header>
  )
}
