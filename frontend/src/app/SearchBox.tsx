import { type FormEvent, type KeyboardEvent, useId, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router'

import Icon from '../components/Icon'
import IconButton from '../components/IconButton'
import { NARROW_HEADER, useMediaQuery } from '../hooks/useMediaQuery'
import { useSuggestions } from '../search/hooks'
import styles from './SearchBox.module.css'

/** YouTube's look: the typed start in regular weight, the rest in bold. */
function Suggestion({ text, typed }: { text: string; typed: string }) {
  const start = typed.trimStart()
  if (start && text.toLowerCase().startsWith(start.toLowerCase())) {
    return (
      <span className={styles.suggestionText}>
        <span className={styles.typed}>{text.slice(0, start.length)}</span>
        {text.slice(start.length)}
      </span>
    )
  }
  return <span className={styles.suggestionText}>{text}</span>
}

export default function SearchBox() {
  const navigate = useNavigate()
  const narrow = useMediaQuery(NARROW_HEADER)
  // Narrow screens: the search bar opens over the whole header.
  const [open, setOpen] = useState(false)
  // On the results page the box shows its query, also after Back and Forward.
  const location = useLocation()
  const shown =
    location.pathname === '/results'
      ? (new URLSearchParams(location.search).get('search_query') ?? '')
      : null
  const [query, setQuery] = useState(shown ?? '')
  const [lastShown, setLastShown] = useState(shown)
  if (shown !== lastShown) {
    setLastShown(shown)
    if (shown !== null) setQuery(shown)
  }
  const input = useRef<HTMLInputElement>(null)

  // What the viewer typed; the arrows put a suggestion in the box but keep this list.
  const [typed, setTyped] = useState('')
  const [listOpen, setListOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const suggestions = useSuggestions(typed).data ?? []
  const showList = listOpen && typed.trim() !== '' && suggestions.length > 0
  const listId = useId()
  const optionId = (index: number) => `${listId}-${index}`

  function go(text: string) {
    const trimmed = text.trim()
    if (!trimmed) return
    navigate(`/results?${new URLSearchParams({ search_query: trimmed })}`)
    input.current?.blur()
    setListOpen(false)
    setOpen(false)
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    go(query)
  }

  function type(value: string) {
    setQuery(value)
    setTyped(value)
    setActive(-1)
    setListOpen(true)
  }

  /** Down and Up go round the list and back to what was typed, as on YouTube. */
  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape' && showList) {
      event.stopPropagation() // the first Escape closes only the list
      setListOpen(false)
      return
    }
    if ((event.key !== 'ArrowDown' && event.key !== 'ArrowUp') || !showList) return
    event.preventDefault()
    const count = suggestions.length + 1 // the last stop is what was typed
    const next = ((active + 1 + (event.key === 'ArrowDown' ? 1 : -1) + count) % count) - 1
    setActive(next)
    setQuery(next === -1 ? typed : suggestions[next])
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
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && active >= 0 ? optionId(active) : undefined}
          placeholder="Search"
          aria-label="Search"
          autoComplete="off"
          // Opened on purpose by the search button.
          autoFocus={narrow}
          value={query}
          onChange={(event) => type(event.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => setListOpen(false)}
        />
        {query && (
          <IconButton
            icon="close"
            label="Clear search query"
            onClick={() => {
              type('')
              input.current?.focus()
            }}
          />
        )}
        <ul
          id={listId}
          className={styles.suggestions}
          role="listbox"
          aria-label="Suggestions"
          hidden={!showList}
        >
          {showList &&
            suggestions.map((text, index) => (
              <li
                key={text}
                id={optionId(index)}
                className={styles.suggestion}
                role="option"
                aria-selected={index === active}
                // Keeps the focus in the box, so the blur doesn't close the list before the click.
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => go(text)}
              >
                <Icon name="search" />
                <Suggestion text={text} typed={typed} />
              </li>
            ))}
        </ul>
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
