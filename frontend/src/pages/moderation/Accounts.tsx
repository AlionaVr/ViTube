import { useState } from 'react'
import { Link } from 'react-router'

import Avatar from '../../components/Avatar'
import ChipBar from '../../components/ChipBar'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Spinner from '../../components/Spinner'
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll'
import type { RestrictedAccount, UserStatus } from '../../moderation/api'
import { useRestrictedAccounts, useSetStatus } from '../../moderation/hooks'
import { isAdmin } from '../../moderation/roles'
import buttons from '../../styles/buttons.module.css'
import { channelUrl } from '../../videos/paths'
import NotFoundPage from '../NotFoundPage'
import styles from './ModerationPage.module.css'
import { useModerator } from './useModerator'

const FILTERS: { id: UserStatus | null; label: string }[] = [
  { id: null, label: 'All' },
  { id: 'banned', label: 'Banned' },
  { id: 'terminated', label: 'Terminated' },
]

const STATUS_LABELS: Record<UserStatus, string> = {
  active: 'Active',
  banned: 'Banned',
  terminated: 'Channel terminated',
}

/** Admins: banned and terminated accounts, newest accounts first, with Reinstate. */
export default function Accounts() {
  const admin = isAdmin(useModerator())
  return admin ? <AccountList /> : <NotFoundPage />
}

function AccountList() {
  const [filter, setFilter] = useState<UserStatus | null>(null)
  const accounts = useRestrictedAccounts(filter)
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => accounts.fetchNextPage(),
    accounts.hasNextPage && !accounts.isFetchingNextPage,
  )

  let body
  if (accounts.isPending) {
    body = (
      <div className={styles.loading}>
        <Spinner />
      </div>
    )
  } else if (accounts.isError) {
    body = <ErrorState title="Couldn't load accounts" onRetry={() => accounts.refetch()} />
  } else {
    const items = accounts.data.pages.flatMap((page) => page.items)
    body =
      items.length === 0 ? (
        <EmptyState title="No restricted accounts">
          Accounts you ban or whose channels you terminate show up here.
        </EmptyState>
      ) : (
        <>
          <ol className={styles.rows} aria-label="Restricted accounts">
            {items.map((account) => (
              <AccountRow key={account.channel.handle} account={account} />
            ))}
          </ol>
          <div ref={sentinel} />
        </>
      )
  }

  return (
    <>
      <div className={styles.filters}>
        <ChipBar chips={FILTERS} selected={filter} onSelect={setFilter} label="Show accounts" />
      </div>
      {body}
    </>
  )
}

function AccountRow({ account }: { account: RestrictedAccount }) {
  const { channel } = account
  const reinstate = useSetStatus()
  return (
    <li className={`${styles.row} ${styles.accountRow}`}>
      <Avatar name={channel.handle} src={channel.avatar_url} size={40} />
      <div className={styles.video}>
        <Link to={channelUrl(channel.handle)} className={styles.author}>
          @{channel.handle}
        </Link>
        <p className={styles.meta}>{STATUS_LABELS[account.status]}</p>
      </div>
      <div className={styles.actions}>
        <button
          type="button"
          className={`${buttons.pill} ${buttons.tonal} ${buttons.small}`}
          aria-label={`Reinstate @${channel.handle}`}
          disabled={reinstate.isPending}
          onClick={() => reinstate.mutate({ handle: channel.handle, status: 'active' })}
        >
          Reinstate
        </button>
        {reinstate.isError && (
          <p className={styles.error} role="alert">
            {reinstate.error.message}
          </p>
        )}
      </div>
    </li>
  )
}
