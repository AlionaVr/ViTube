import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderApp } from '../test/render'
import { intersectAll } from '../test/observers'
import { listVideos } from '../videos/api'

vi.mock('../videos/api', async (importOriginal) => {
  const api = await importOriginal<typeof import('../videos/api')>()
  return { ...api, listVideos: vi.fn(api.listVideos) }
})

const cards = () => screen.getAllByRole('article')

describe('HomePage', () => {
  it('shows skeletons, then cards with channel, views and age', async () => {
    renderApp('/')
    expect(screen.getByLabelText('Loading videos')).toHaveAttribute('aria-busy', 'true')

    const link = await screen.findByRole('link', { name: 'Big Buck Bunny – trailer' })
    expect(link).toHaveAttribute('href', expect.stringMatching(/^\/watch\?v=[\w-]{11}$/))
    const card = cards()[0]
    expect(within(card).getByRole('link', { name: 'Open Movie Club' })).toHaveAttribute(
      'href',
      '/@openmovieclub',
    )
    expect(within(card).getByText(/^2\.3M views • 3 years ago$/)).toBeInTheDocument()
    expect(within(card).getByText('0:33')).toBeInTheDocument()
  })

  it('loads the next page when the end of the grid comes into view', async () => {
    renderApp('/')
    await screen.findByRole('link', { name: 'Big Buck Bunny – trailer' })
    expect(cards()).toHaveLength(12)

    act(() => intersectAll())
    expect(await screen.findByRole('status', { name: 'Loading more videos' })).toBeInTheDocument()
    await screen.findByRole('link', { name: 'Open movies you can legally remix' })
    expect(cards()).toHaveLength(24)
  })

  it('filters by a chip', async () => {
    renderApp('/')
    const all = await screen.findByRole('button', { name: 'All' })
    expect(all).toHaveAttribute('aria-pressed', 'true')

    await userEvent.click(screen.getByRole('button', { name: 'Nature' }))
    expect(screen.getByRole('button', { name: 'Nature' })).toHaveAttribute('aria-pressed', 'true')
    await screen.findByRole('link', { name: 'Flower opening' })
    expect(screen.queryByRole('link', { name: 'Sintel – trailer' })).not.toBeInTheDocument()
  })

  it('offers a retry when the feed fails to load', async () => {
    vi.mocked(listVideos).mockRejectedValueOnce(new Error('offline'))
    renderApp('/')

    expect(await screen.findByRole('alert')).toHaveTextContent('Can’t load videos')
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('link', { name: 'Sintel – trailer' })).toBeInTheDocument()
  })
})
