import { Link } from 'react-router'

import { useSubscriptions } from '../../channels/hooks'
import SubscribeButton from '../../channels/SubscribeButton'
import type { SubscribedChannel } from '../../channels/types'
import Avatar from '../../components/Avatar'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Spinner from '../../components/Spinner'
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll'
import { NARROW_HEADER, useMediaQuery } from '../../hooks/useMediaQuery'
import { formatSubscribers } from '../../lib/format'
import { channelUrl } from '../../videos/paths'
import { useViewer } from '../../viewer/useViewer'
import styles from './ChannelsPage.module.css'
import SignInToSee from './SignInToSee'

function Row({ channel }: { channel: SubscribedChannel }) {
  const narrow = useMediaQuery(NARROW_HEADER)
  const url = channelUrl(channel.handle)
  return (
    <li className={styles.row}>
      <Link to={url} className={styles.avatar} tabIndex={-1} aria-hidden="true">
        <Avatar name={channel.name} src={channel.avatar_url} size={narrow ? 64 : 136} />
      </Link>
      <div className={styles.text}>
        <Link to={url} className={styles.name}>
          {channel.name}
        </Link>
        <p className={styles.meta}>
          @{channel.handle} • {formatSubscribers(channel.subscriber_count)}
        </p>
      </div>
      {/* Every row is a subscription; an unsubscribed one leaves the list. */}
      <SubscribeButton channel={{ ...channel, is_subscribed: true }} />
    </li>
  )
}

function Subscriptions() {
  const subscriptions = useSubscriptions()
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => void subscriptions.fetchNextPage(),
    subscriptions.hasNextPage &&
      !subscriptions.isFetchingNextPage &&
      !subscriptions.isFetchNextPageError,
  )
  const channels = subscriptions.data?.pages.flatMap((page) => page.items) ?? []

  if (subscriptions.isPending) return <Spinner label="Loading subscriptions" />
  if (!subscriptions.data) {
    return (
      <ErrorState
        title="Can’t load your subscriptions"
        onRetry={() => void subscriptions.refetch()}
      />
    )
  }
  if (channels.length === 0) {
    return (
      <EmptyState title="No subscriptions yet">Channels you subscribe to appear here.</EmptyState>
    )
  }
  return (
    <>
      <ul className={styles.list}>
        {channels.map((channel) => (
          <Row key={channel.handle} channel={channel} />
        ))}
      </ul>
      <div ref={sentinel} />
      {subscriptions.isFetchingNextPage && <Spinner label="Loading more subscriptions" />}
      {subscriptions.isFetchNextPageError && (
        <ErrorState
          title="Can’t load more subscriptions"
          onRetry={() => void subscriptions.fetchNextPage()}
        />
      )}
    </>
  )
}

/** /feed/channels: every channel the viewer subscribed to, A to Z. */
export default function ChannelsPage() {
  const viewer = useViewer()
  return (
    <div className={styles.page}>
      <title>All subscriptions - ViTube</title>
      {viewer.status === 'guest' ? (
        <SignInToSee />
      ) : (
        viewer.status === 'authenticated' && (
          <>
            <h1 className={styles.title}>All subscriptions</h1>
            <Subscriptions />
          </>
        )
      )}
    </div>
  )
}
