import {render, screen} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {createMemoryRouter} from 'react-router'
import {RouterProvider} from 'react-router/dom'
import {describe, expect, it, vi} from 'vitest'

import {routes} from './routes'

function renderAt(path: string) {
    const router = createMemoryRouter(routes, {initialEntries: [path]})
    render(<RouterProvider router={router}/>)
    return router
}

describe('Layout', () => {
    it('collapses the sidebar to mini mode and back', async () => {
        renderAt('/')
        const menu = screen.getByRole('button', {name: 'Menu'})
        expect(menu).toHaveAttribute('aria-expanded', 'true')
        expect(screen.getByRole('link', {name: 'History'})).toBeInTheDocument()

        await userEvent.click(menu)
        expect(menu).toHaveAttribute('aria-expanded', 'false')
        expect(screen.queryByRole('link', {name: 'History'})).not.toBeInTheDocument()
        expect(screen.getByRole('link', {name: 'Home'})).toBeInTheDocument()

        await userEvent.click(menu)
        expect(menu).toHaveAttribute('aria-expanded', 'true')
    })

    it('starts with the mini sidebar on narrower screens', () => {
        const wide = window.matchMedia('')
        vi.spyOn(window, 'matchMedia').mockReturnValue({...wide, matches: false})

        renderAt('/')
        expect(screen.getByRole('button', {name: 'Menu'})).toHaveAttribute('aria-expanded', 'false')
    })

    it('submits search to the YouTube-style results URL', async () => {
        const router = renderAt('/')
        await userEvent.type(screen.getByRole('searchbox', {name: 'Search'}), ' cats & dogs {Enter}')

        expect(router.state.location.pathname).toBe('/results')
        expect(router.state.location.search).toBe('?search_query=cats+%26+dogs')
    })

    it('shows the not-found page for unknown paths', () => {
        renderAt('/no-such-page')
        expect(screen.getByText("This page isn't available")).toBeInTheDocument()
    })
})
