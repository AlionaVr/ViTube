import {useEffect, useState} from 'react'
import {Outlet} from 'react-router'

import Header from './Header'
import styles from './Layout.module.css'
import Sidebar from './Sidebar'

// Like YouTube: the full sidebar on wide screens, the mini one below this width.
const WIDE_SCREEN = '(min-width: 1313px)'

export default function Layout() {
    const [sidebarExpanded, setSidebarExpanded] = useState(
        () => window.matchMedia(WIDE_SCREEN).matches,
    )

    useEffect(() => {
        const query = window.matchMedia(WIDE_SCREEN)
        const onChange = (event: MediaQueryListEvent) => setSidebarExpanded(event.matches)
        query.addEventListener('change', onChange)
        return () => query.removeEventListener('change', onChange)
    }, [])

    return (
        <>
            <Header
                sidebarExpanded={sidebarExpanded}
                onMenuClick={() => setSidebarExpanded((expanded) => !expanded)}
            />
            <Sidebar expanded={sidebarExpanded}/>
            <main
                className={`${styles.main} ${sidebarExpanded ? styles.withSidebar : styles.withMiniSidebar}`}
            >
                <Outlet/>
            </main>
        </>
    )
}
