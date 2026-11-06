import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { renderApp } from '../test/render'
import { setScreenWidth } from '../test/screen'

describe('SearchBox', () => {
  it('submits to the YouTube-style results URL', async () => {
    const router = renderApp('/')
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search' }), ' cats & dogs {Enter}')

    expect(router.state.location.pathname).toBe('/results')
    expect(router.state.location.search).toBe('?search_query=cats+%26+dogs')
  })

  it('ignores an empty query', async () => {
    const router = renderApp('/')
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search' }), '   {Enter}')
    expect(router.state.location.pathname).toBe('/')
  })

  it('clears the query and keeps the focus in the box', async () => {
    renderApp('/')
    const box = screen.getByRole('searchbox', { name: 'Search' })
    expect(screen.queryByRole('button', { name: 'Clear search query' })).not.toBeInTheDocument()

    await userEvent.type(box, 'sintel')
    await userEvent.click(screen.getByRole('button', { name: 'Clear search query' }))

    expect(box).toHaveValue('')
    expect(box).toHaveFocus()
  })

  it('folds into an icon on narrow screens and opens over the header', async () => {
    setScreenWidth(400)
    const router = renderApp('/')
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    const box = screen.getByRole('searchbox', { name: 'Search' })
    expect(box).toHaveFocus()

    await userEvent.click(screen.getByRole('button', { name: 'Back' }))
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    await userEvent.type(screen.getByRole('searchbox'), 'dragon{Enter}')
    expect(router.state.location.search).toBe('?search_query=dragon')
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument()
  })
})
