import { useState } from 'react'
import { Outlet, ScrollRestoration, useLocation } from 'react-router'

import { ToastProvider } from '../components/Toast'
import { useMediaQuery, WIDE_SCREEN } from '../hooks/useMediaQuery'
import { useStoredFlag } from '../hooks/useStoredFlag'
import GuideDrawer from './GuideDrawer'
import Header from './Header'
import styles from './Layout.module.css'
import { FullGuide, MiniGuide } from './Sidebar'

export default function Layout() {
  const wide = useMediaQuery(WIDE_SCREEN)
  const watchPage = useLocation().pathname === '/watch'
  // Like YouTube: on wide screens the guide sits next to the content, full or mini.
  // Narrower, and always on the watch page, the menu button opens it over the page.
  const persistent = wide && !watchPage
  const [fullGuide, toggleFullGuide] = useStoredFlag('vitube:full-guide', true)
  const [drawerOpen, setDrawerOpen] = useState(false)

  const guide = persistent && fullGuide ? 'full' : watchPage ? 'none' : 'mini'
  const offset = { full: styles.full, mini: styles.mini, none: '' }[guide]

  return (
    <ToastProvider>
      <Header
        sidebarExpanded={persistent ? fullGuide : drawerOpen}
        onMenuClick={() => (persistent ? toggleFullGuide() : setDrawerOpen(true))}
      />
      {guide === 'full' && <FullGuide />}
      {guide === 'mini' && <MiniGuide id={persistent ? 'guide' : undefined} />}
      {!persistent && <GuideDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />}
      <main className={`${styles.main} ${offset}`}>
        <Outlet />
      </main>
      {/* A new page starts at the top; Back returns to where you were. */}
      <ScrollRestoration />
    </ToastProvider>
  )
}
