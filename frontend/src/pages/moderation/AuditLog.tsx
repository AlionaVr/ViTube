import { type FormEvent, type ReactNode, useId, useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import Avatar from '../../components/Avatar'
import ChipBar, { type Chip } from '../../components/ChipBar'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Icon from '../../components/Icon'
import Spinner from '../../components/Spinner'
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll'
import { formatDate, formatTimeAgo } from '../../lib/format'
import type { AuditAction, AuditEntry, AuditFilters, ReportReason } from '../../moderation/api'
import { useAuditLog } from '../../moderation/hooks'
import { REASON_LABELS } from '../../moderation/reasons'
import { isAdmin } from '../../moderation/roles'
import buttons from '../../styles/buttons.module.css'
import { channelUrl, watchUrl } from '../../videos/paths'
import NotFoundPage from '../NotFoundPage'
import styles from './ModerationPage.module.css'
import { useModerator } from './useModerator'

/** The action chips; a chip may stand for several actions. */
const GROUPS = {
  hidden: { label: 'Hidden', actions: ['hide_video'] },
  restored: { label: 'Restored', actions: ['restore_video'] },
  dismissed: { label: 'Dismissed', actions: ['dismiss_video', 'dismiss_comment'] },
  deleted: { label: 'Comments deleted', actions: ['delete_comment'] },
  status: { label: 'Account status', actions: ['set_user_status'] },
  roles: { label: 'Roles', actions: ['set_user_role'] },
} satisfies Record<string, { label: string; actions: AuditAction[] }>

type Group = keyof typeof GROUPS

const CHIPS: Chip<Group>[] = [
  { id: null, label: 'All' },
  ...(Object.keys(GROUPS) as Group[]).map((id) => ({ id, label: GROUPS[id].label })),
]

const HANDLE = /^[A-Za-z0-9._-]{3,30}$/ // the users.handle rule

const isGroup = (value: string | null): value is Group => value !== null && value in GROUPS

/** Admins: every moderator and admin action, newest first (ADR 0009). */
export default function AuditLog() {
  return isAdmin(useModerator()) ? <FilteredLog /> : <NotFoundPage />
}

/** The filters live in the URL, so a filtered log can be shared and survives a reload. */
function FilteredLog() {
  const [params, setParams] = useSearchParams()
  const group = params.get('action')
  const cli = params.get('source') === 'cli'
  const filters: AuditFilters = {
    actions: isGroup(group) ? GROUPS[group].actions : [],
    source: cli ? 'cli' : null,
    actor: cli ? null : params.get('by') || null,
    account: params.get('about') || null,
  }
  const filtered =
    filters.actions.length > 0 || cli || filters.actor !== null || filters.account !== null

  const update = (changes: Record<string, string | null>) =>
    setParams((current) => {
      const next = new URLSearchParams(current)
      for (const [name, value] of Object.entries(changes)) {
        if (value) next.set(name, value)
        else next.delete(name)
      }
      return next
    })
  const clear = () => setParams({})

  return (
    <>
      <div className={styles.filters}>
        <ChipBar
          chips={CHIPS}
          selected={isGroup(group) ? group : null}
          onSelect={(id) => update({ action: id })}
          label="Show actions"
        />
      </div>
      <div className={styles.auditFilters}>
        <HandleFilter
          label="Done by"
          value={filters.actor}
          disabled={cli}
          onApply={(handle) => update({ by: handle })}
        />
        <button
          type="button"
          className={styles.toggle}
          aria-pressed={cli}
          onClick={() => update({ source: cli ? null : 'cli', by: null })}
        >
          <Icon name="settings" size={18} />
          Command line
        </button>
        <HandleFilter
          label="About account"
          value={filters.account}
          onApply={(handle) => update({ about: handle })}
        />
        {filtered && (
          <button
            type="button"
            className={`${buttons.pill} ${buttons.text} ${buttons.small} ${styles.clear}`}
            onClick={clear}
          >
            Clear filters
          </button>
        )}
      </div>
      <EntryList filters={filters} filtered={filtered} onClear={clear} />
    </>
  )
}

/** A handle typed with or without the @; Enter or leaving the field applies it. */
function HandleFilter({
  label,
  value,
  disabled = false,
  onApply,
}: {
  label: string
  value: string | null
  disabled?: boolean
  onApply: (handle: string | null) => void
}) {
  const id = useId()
  const [draft, setDraft] = useState(value ?? '')
  const [shown, setShown] = useState(value)
  const [error, setError] = useState<string | null>(null)
  // The URL changed elsewhere (a chip, Clear filters, Back): show its value.
  if (value !== shown) {
    setShown(value)
    setDraft(value ?? '')
    setError(null)
  }

  function apply() {
    const handle = draft.trim().replace(/^@/, '')
    if (handle && !HANDLE.test(handle)) {
      setError('Enter a handle, like @name')
      return
    }
    setError(null)
    if (handle !== (value ?? '')) onApply(handle || null)
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    apply()
  }

  return (
    <form className={styles.handleFilter} onSubmit={submit} noValidate>
      <label htmlFor={id}>{label}</label>
      <div className={styles.handleBox} data-invalid={error ? true : undefined}>
        <span aria-hidden>@</span>
        <input
          id={id}
          value={draft}
          disabled={disabled}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={apply}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          autoComplete="off"
          spellCheck={false}
        />
      </div>
      {error && (
        <p id={`${id}-error`} className={styles.filterError}>
          {error}
        </p>
      )}
    </form>
  )
}

function EntryList({
  filters,
  filtered,
  onClear,
}: {
  filters: AuditFilters
  filtered: boolean
  onClear: () => void
}) {
  const log = useAuditLog(filters)
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => log.fetchNextPage(),
    log.hasNextPage && !log.isFetchingNextPage,
  )

  if (log.isPending) {
    return (
      <div className={styles.loading}>
        <Spinner />
      </div>
    )
  }
  if (log.isError) {
    return <ErrorState title="Couldn't load the audit log" onRetry={() => log.refetch()} />
  }
  const entries = log.data.pages.flatMap((page) => page.items)
  if (entries.length === 0) {
    return filtered ? (
      <EmptyState title="No entries match these filters">
        <button type="button" className={`${buttons.pill} ${buttons.tonal}`} onClick={onClear}>
          Clear filters
        </button>
      </EmptyState>
    ) : (
      <EmptyState title="Nothing logged yet">
        What moderators and admins do shows up here.
      </EmptyState>
    )
  }
  return (
    <>
      <ol className={styles.rows} aria-label="Audit log">
        {entries.map((entry) => (
          <EntryRow key={entry.id} entry={entry} />
        ))}
      </ol>
      <div ref={sentinel} />
      {log.isFetchingNextPage && (
        <div className={styles.loading}>
          <Spinner />
        </div>
      )}
    </>
  )
}

function EntryRow({ entry }: { entry: AuditEntry }) {
  const { actor } = entry
  // No actor: the command line, or an account deleted since (the log keeps no foreign keys).
  const cli = entry.source === 'cli'
  return (
    <li className={`${styles.row} ${styles.auditRow}`}>
      {actor ? (
        <Avatar name={actor.handle} src={actor.avatar_url} size={32} />
      ) : (
        <span className={styles.cliMark} aria-hidden>
          <Icon name={cli ? 'settings' : 'account'} size={20} />
        </span>
      )}
      <div className={styles.video}>
        <p className={styles.auditText}>
          {actor ? (
            <Link to={channelUrl(actor.handle)} className={styles.author}>
              @{actor.handle}
            </Link>
          ) : (
            <span className={styles.author}>{cli ? 'Command line' : 'A deleted account'}</span>
          )}{' '}
          <Sentence entry={entry} />
        </p>
        <Details entry={entry} />
      </div>
      <time
        className={`${styles.meta} ${styles.auditTime}`}
        dateTime={entry.created_at}
        title={formatDate(entry.created_at)}
      >
        {formatTimeAgo(entry.created_at)}
      </time>
    </li>
  )
}

/** What happened, in words, with a link to what it happened to. */
function Sentence({ entry }: { entry: AuditEntry }) {
  const { target, details } = entry
  let link: ReactNode = <span className={styles.gone}>(deleted)</span>
  if (target.label && target.video_id) {
    link = (
      <Link to={watchUrl(target.video_id)} className={styles.inlineLink}>
        “{target.label}”
      </Link>
    )
  } else if (target.handle) {
    link = (
      <Link to={channelUrl(target.handle)} className={styles.inlineLink}>
        {target.label}
      </Link>
    )
  }
  switch (entry.action) {
    case 'hide_video':
      return <>hid {link}</>
    case 'restore_video':
      return <>restored {link}</>
    case 'dismiss_video':
      return <>dismissed reports on {link}</>
    case 'delete_comment':
      return <>deleted the comment {link}</>
    case 'dismiss_comment':
      return <>dismissed reports on the comment {link}</>
    case 'set_user_role':
      return (
        <>
          made {link} {String(details.to)} (was {String(details.from)})
        </>
      )
    case 'set_user_status':
      if (details.to === 'banned') return <>banned {link}</>
      if (details.to === 'terminated') return <>terminated the channel {link}</>
      return <>reinstated {link}</>
  }
}

/** The reason, what else the action touched, and who ran a command. */
function Details({ entry }: { entry: AuditEntry }) {
  const { details } = entry
  const parts: string[] = []
  if (entry.action === 'hide_video' && typeof details.reason === 'string') {
    parts.push(REASON_LABELS[details.reason as ReportReason] ?? details.reason)
  } else if (typeof details.reason === 'string') {
    parts.push(`“${details.reason}”`)
  }
  if (typeof details.reports === 'number' && details.reports > 0) {
    parts.push(details.reports === 1 ? '1 report closed' : `${details.reports} reports closed`)
  }
  if (typeof details.replies === 'number' && details.replies > 0) {
    parts.push(details.replies === 1 ? '1 reply deleted' : `${details.replies} replies deleted`)
  }
  if (entry.source === 'cli' && entry.by) parts.push(`Run by ${entry.by}`)
  return parts.length > 0 ? <p className={styles.meta}>{parts.join('. ')}</p> : null
}
