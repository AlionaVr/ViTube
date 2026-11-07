import { type FormEvent, useRef, useState } from 'react'
import { useNavigate } from 'react-router'

import Icon from '../components/Icon'
import IconButton from '../components/IconButton'
import { NARROW_HEADER, useMediaQuery } from '../hooks/useMediaQuery'
import styles from './SearchBox.module.css'

export default function SearchBox() {
  const navigate = useNavigate()
  const narrow = useMediaQuery(NARROW_HEADER)
  // Narrow screens: the search bar opens over the whole header.
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const input = useRef<HTMLInputElement>(null)

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const trimmed = query.trim()
    if (!trimmed) return
    navigate(`/results?${new URLSearchParams({ search_query: trimmed })}`)
    input.current?.blur()
    setOpen(false)
  }

  if (narrow && !open) {
    return <IconButton icon="search" label="Search" onClick={() => setOpen(true)} />
  }

  const form = (
    <form className={styles.search} role="search" onSubmit={handleSubmit}>
      <div className={styles.box}>
        <span className={styles.icon}>
          <Icon name="search" size={20} />
        </span>
        <input
          ref={input}
          className={styles.input}
          type="search"
          placeholder="Search"
          aria-label="Search"
          autoComplete="off"
          // Opened on purpose by the search button.
          autoFocus={narrow}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        {query && (
          <IconButton
            icon="close"
            label="Clear search query"
            onClick={() => {
              setQuery('')
              input.current?.focus()
            }}
          />
        )}
      </div>
      <button type="submit" className={styles.submit} aria-label="Search" title="Search">
        <Icon name="search" />
      </button>
    </form>
  )

  if (!narrow) return form
  return (
    <div
      className={styles.overlay}
      onKeyDown={(event) => {
        if (event.key === 'Escape') setOpen(false)
      }}
    >
      <IconButton icon="arrowBack" label="Back" onClick={() => setOpen(false)} />
      {form}
    </div>
  )
}
