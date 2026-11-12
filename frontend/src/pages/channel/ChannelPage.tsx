import '@fontsource/roboto/700.css'

import { useState } from 'react'
import { Link, Outlet, useLocation, useParams } from 'react-router'

import { ApiError } from '../../api/client'
import { useChannel } from '../../channels/hooks'
import SubscribeButton from '../../channels/SubscribeButton'
import type { Channel } from '../../channels/types'
import Avatar from '../../components/Avatar'
import ErrorState from '../../components/ErrorState'
import ModerationNotice from '../../components/ModerationNotice'
import { NARROW_HEADER, useMediaQuery } from '../../hooks/useMediaQuery'
import { formatSubscribers, formatVideoCount } from '../../lib/format'
import { isAdmin } from '../../moderation/roles'
import buttons from '../../styles/buttons.module.css'
import { useViewer } from '../../viewer/useViewer'
import RestrictDialog from '../moderation/RestrictDialog'
import RowMenu from '../moderation/RowMenu'
import NotFoundPage from '../NotFoundPage'
import styles from './ChannelPage.module.css'

// The users.handle rule. A malformed one can't exist, so it needs no request.
const HANDLE = /^[A-Za-z0-9._-]{3,30}$/

function Header({ channel }: { channel: Channel }) {
  const viewer = useViewer()
  const narrow = useMediaQuery(NARROW_HEADER)
  const own = viewer.status === 'authenticated' && viewer.user.handle === channel.handle
  // Admins restrict an account from its channel too, not only from a report on its content.
  const admin = viewer.status === 'authenticated' && isAdmin(viewer.user) && !own
  const [restricting, setRestricting] = useState(false)

  return (
    <header className={styles.header}>
      <Avatar name={channel.name} src={channel.avatar_url} size={narrow ? 72 : 160} />
      <div className={styles.info}>
        <h1 className={styles.name}>{channel.name}</h1>
        <p className={styles.meta}>
          <span className={styles.handle}>@{channel.handle}</span>
          {' • '}
          {formatSubscribers(channel.subscriber_count)}
          {' • '}
          {formatVideoCount(channel.video_count)}
        </p>
        {/* Nothing until we know who is watching: the owner never sees a Subscribe flash by.
            A terminated channel is frozen: no Subscribe. */}
        {(!channel.is_terminated || admin) && (
          <div className={styles.actions}>
            {viewer.status !== 'loading' && !own && !channel.is_terminated && (
              <SubscribeButton channel={channel} />
            )}
            {/* As on YouTube; no "Customize channel": channels can't be edited yet. */}
            {own && (
              <Link to="/studio/videos" className={`${buttons.pill} ${buttons.tonal}`}>
                Manage videos
              </Link>
            )}
            {admin && <RowMenu account={channel} onRestrict={() => setRestricting(true)} />}
          </div>
        )}
      </div>
      {admin && (
        <RestrictDialog
          target={restricting ? channel : null}
          onClose={() => setRestricting(false)}
        />
      )}
    </header>
  )
}

function HeaderSkeleton() {
  return (
    <div className={styles.header} aria-busy="true" aria-label="Loading channel">
      <div className={`${styles.ghost} ${styles.ghostAvatar}`} />
      <div className={styles.info}>
        <div className={`${styles.ghost} ${styles.ghostName}`} />
        <div className={`${styles.ghost} ${styles.ghostLine}`} />
      </div>
    </div>
  )
}

// /@handle itself shows the first tab, as YouTube's /@handle shows its first one (Home).
const TABS = [
  { path: 'videos', label: 'Videos' },
  { path: 'playlists', label: 'Playlists' },
]

function Tabs({ handle }: { handle: string }) {
  const { pathname } = useLocation()
  const current = pathname.split('/')[2] || TABS[0].path // "/@anna/videos" → "videos"
  return (
    <nav className={styles.tabs} aria-label="Channel">
      {TABS.map((tab) => (
        <Link
          key={tab.path}
          to={`/@${handle}/${tab.path}`}
          className={styles.tab}
          aria-current={tab.path === current ? 'page' : undefined}
        >
          {tab.label}
        </Link>
      ))}
    </nav>
  )
}

function ChannelView({ handle }: { handle: string }) {
  const channel = useChannel(handle)

  if (channel.error instanceof ApiError && channel.error.status === 404) return <NotFoundPage />
  return (
    <div className={styles.page}>
      <title>{channel.data ? `${channel.data.name} - ViTube` : 'ViTube'}</title>
      {channel.isError ? (
        <ErrorState title="Can’t load this channel" onRetry={() => void channel.refetch()} />
      ) : (
        <>
          {channel.data ? <Header channel={channel.data} /> : <HeaderSkeleton />}
          {/* Only moderators open a terminated channel (ADR 0009). */}
          {channel.data?.is_terminated && (
            <ModerationNotice title="Channel terminated" className={styles.notice}>
              Only moderators can see this channel. Its videos are left out of lists, and
              subscribing is off until an admin reinstates it.
            </ModerationNotice>
          )}
          <Tabs handle={handle} />
          {/* The tab loads with the header, not after it. */}
          <Outlet context={handle} />
        </>
      )}
    </div>
  )
}

/** /@handle. The router has no partial segments, so the "@" is checked here. */
export default function ChannelPage() {
  const { channel = '' } = useParams()
  const handle = channel.startsWith('@') ? channel.slice(1) : ''
  if (!HANDLE.test(handle)) return <NotFoundPage />
  return <ChannelView key={handle.toLowerCase()} handle={handle} />
}
