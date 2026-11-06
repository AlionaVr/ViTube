import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { useMe } from '../auth/hooks'
import Icon from '../components/Icon'
import Logo from '../components/Logo'
import SignInButton from '../components/SignInButton'
import AccountMenu from './AccountMenu'
import styles from './Header.module.css'

interface HeaderProps {
  sidebarExpanded: boolean
  onMenuClick: () => void
}

export default function Header({ sidebarExpanded, onMenuClick }: HeaderProps) {
  const navigate = useNavigate()
  const me = useMe()
  const [query, setQuery] = useState('')

  function handleSearch(event: FormEvent) {
    event.preventDefault()
    const trimmed = query.trim()
    if (trimmed) {
      navigate(`/results?${new URLSearchParams({ search_query: trimmed })}`)
    }
  }

  return (
    <header className={styles.header}>
      <div className={styles.start}>
        <button
          type="button"
          className={styles.iconButton}
          aria-label="Menu"
          aria-expanded={sidebarExpanded}
          aria-controls="guide"
          onClick={onMenuClick}
        >
          <Icon name="menu" />
        </button>
        <Link to="/" className={styles.logo} aria-label="ViTube home">
          <Logo />
        </Link>
      </div>

      <form className={styles.search} role="search" onSubmit={handleSearch}>
        <input
          className={styles.searchInput}
          type="search"
          placeholder="Search"
          aria-label="Search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <button type="submit" className={styles.searchButton} aria-label="Search">
          <Icon name="search" />
        </button>
      </form>

      <div className={styles.end}>
        {/* Nothing until /me answers: no "Sign in" flash for signed-in users. */}
        {me.data ? <AccountMenu user={me.data} /> : !me.isPending && <SignInButton />}
      </div>
    </header>
  )
}
