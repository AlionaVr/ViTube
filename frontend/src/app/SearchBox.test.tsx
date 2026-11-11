import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import { json, mockApi } from '../test/api'
import { renderApp } from '../test/render'
import { setScreenWidth } from '../test/screen'

const GUEST = { 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) }

describe('SearchBox', () => {
  beforeEach(() => {
    mockApi({ ...GUEST, 'GET /api/search/suggestions': () => json(200, []) })
  })
  it('submits to the YouTube-style results URL', async () => {
    const router = renderApp('/')
    await userEvent.type(screen.getByRole('combobox', { name: 'Search' }), ' cats & dogs {Enter}')

    expect(router.state.location.pathname).toBe('/results')
    expect(router.state.location.search).toBe('?search_query=cats+%26+dogs')
  })

  it('shows the query of the results page, also after going back', async () => {
    const router = renderApp('/results?search_query=sintel')
    const box = screen.getByRole('combobox', { name: 'Search' })
    expect(box).toHaveValue('sintel')

    await act(() => router.navigate('/results?search_query=big+buck+bunny'))
    expect(box).toHaveValue('big buck bunny')
    await act(() => router.navigate(-1))
    expect(box).toHaveValue('sintel')
  })

  it('suggests titles while typing and searches the one clicked', async () => {
    const fetch = mockApi({
      ...GUEST,
      'GET /api/search/suggestions': () => json(200, ['Sintel – trailer', 'The Sintel story']),
    })
    const router = renderApp('/')
    const box = screen.getByRole('combobox', { name: 'Search' })
    await userEvent.type(box, 'sin')

    const list = await screen.findByRole('listbox', { name: 'Suggestions' })
    expect(box).toHaveAttribute('aria-expanded', 'true')
    const options = within(list).getAllByRole('option')
    expect(options.map((option) => option.textContent)).toEqual([
      'Sintel – trailer',
      'The Sintel story',
    ])
    // Asked once, after the pause in typing.
    const asked = fetch.mock.calls
      .map(([request]) => new URL(request.url))
      .filter((url) => url.pathname === '/api/search/suggestions')
    expect(asked.map((url) => url.search)).toEqual(['?q=sin'])

    await userEvent.click(options[1])
    expect(router.state.location.search).toBe('?search_query=The+Sintel+story')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('walks the suggestions with the arrows and closes them with Escape', async () => {
    mockApi({ ...GUEST, 'GET /api/search/suggestions': () => json(200, ['Sintel', 'Sinbad']) })
    const router = renderApp('/')
    const box = screen.getByRole('combobox', { name: 'Search' })
    await userEvent.type(box, 'sin')
    await screen.findByRole('listbox')

    await userEvent.keyboard('{ArrowDown}{ArrowDown}')
    expect(box).toHaveValue('Sinbad')
    expect(screen.getByRole('option', { name: 'Sinbad' })).toHaveAttribute('aria-selected', 'true')
    await userEvent.keyboard('{ArrowDown}')
    expect(box).toHaveValue('sin')
    await userEvent.keyboard('{ArrowUp}')
    expect(box).toHaveValue('Sinbad')

    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    expect(box).toHaveValue('Sinbad')
    await userEvent.keyboard('{Enter}')
    expect(router.state.location.search).toBe('?search_query=Sinbad')
  })

  it('ignores an empty query', async () => {
    const router = renderApp('/')
    await userEvent.type(screen.getByRole('combobox', { name: 'Search' }), '   {Enter}')
    expect(router.state.location.pathname).toBe('/')
  })

  it('clears the query and keeps the focus in the box', async () => {
    renderApp('/')
    const box = screen.getByRole('combobox', { name: 'Search' })
    expect(screen.queryByRole('button', { name: 'Clear search query' })).not.toBeInTheDocument()

    await userEvent.type(box, 'sintel')
    await userEvent.click(screen.getByRole('button', { name: 'Clear search query' }))

    expect(box).toHaveValue('')
    expect(box).toHaveFocus()
  })

  it('folds into an icon on narrow screens and opens over the header', async () => {
    setScreenWidth(400)
    const router = renderApp('/')
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    const box = screen.getByRole('combobox', { name: 'Search' })
    expect(box).toHaveFocus()

    await userEvent.click(screen.getByRole('button', { name: 'Back' }))
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    await userEvent.type(screen.getByRole('combobox'), 'dragon{Enter}')
    expect(router.state.location.search).toBe('?search_query=dragon')
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })
})
