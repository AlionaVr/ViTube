import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { ANNA, json, mockApi } from '../../test/api'
import { listVideos } from '../../videos/api'
import { resetMockServer } from '../../mocks/server'
import { renderApp } from '../../test/render'
import { setScreenWidth } from '../../test/screen'

async function firstVideoId(title: string) {
  const { items } = await listVideos({ category: null, cursor: null })
  return items.find((video) => video.title === title)!.id
}

async function openWatch(title = 'Sintel – trailer') {
  const id = await firstVideoId(title)
  const router = renderApp(`/watch?v=${id}`)
  await screen.findByRole('heading', { level: 1, name: title })
  return router
}

describe('WatchPage', () => {
  beforeEach(() => {
    mockApi({ 'GET /api/auth/me': () => json(200, ANNA) })
  })
  afterEach(() => {
    resetMockServer()
    localStorage.clear()
  })

  it('shows the video, its channel, description and Up next', async () => {
    await openWatch()
    expect(screen.getByRole('region', { name: 'Video player' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open Movie Club' })).toHaveAttribute(
      'href',
      '/@openmovieclub',
    )
    expect(screen.getByText('182K subscribers')).toBeInTheDocument()
    expect(document.title).toBe('Sintel – trailer - ViTube')

    const upNext = await screen.findByRole('region', { name: 'Up next' })
    expect(within(upNext).getAllByRole('link').length).toBeGreaterThan(5)
  })

  it('likes and unlikes at once, with the count', async () => {
    await openWatch()
    const like = screen.getByRole('button', { name: /^Like this video along with/ })
    expect(like).toHaveAttribute('aria-pressed', 'false')
    const before = like.textContent

    await userEvent.click(like)
    expect(like).toHaveAttribute('aria-pressed', 'true')
    expect(like.getAttribute('aria-label')).not.toBe(`Like this video along with ${before}`)

    await userEvent.click(screen.getByRole('button', { name: 'Dislike this video' }))
    expect(screen.getByRole('button', { name: 'Dislike this video' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(like).toHaveAttribute('aria-pressed', 'false')
  })

  it('subscribes, and unsubscribes after a confirmation', async () => {
    await openWatch()
    await userEvent.click(screen.getByRole('button', { name: 'Subscribe' }))
    expect(await screen.findByText('182K subscribers')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Subscribed/ }))
    const dialog = screen.getByRole('dialog', { name: 'Unsubscribe' })
    expect(dialog).toHaveTextContent('Unsubscribe from Open Movie Club?')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Unsubscribe' }))
    expect(await screen.findByRole('button', { name: 'Subscribe' })).toBeInTheDocument()
  })

  it('expands and collapses the description', async () => {
    await openWatch()
    await userEvent.click(screen.getByRole('button', { name: '...more' }))
    expect(screen.getByText(/^1,920,441 views$/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Show less' }))
    expect(screen.getByText('1.9M views')).toBeInTheDocument()
  })

  it('posts a comment at the top of the list', async () => {
    await openWatch()
    const box = await screen.findByRole('textbox', { name: 'Add a comment…' })
    await userEvent.click(box)
    const submit = screen.getByRole('button', { name: 'Comment' })
    expect(submit).toBeDisabled()

    await userEvent.type(box, 'Beautiful trailer!')
    await userEvent.click(submit)

    const first = (await screen.findAllByRole('article'))[0]
    await within(first).findByText('Beautiful trailer!')
    expect(within(first).getByText(`@${ANNA.handle}`)).toBeInTheDocument()
    expect(box).toHaveValue('')
  })

  it('asks a guest to sign in instead of liking', async () => {
    mockApi({ 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) })
    await openWatch()

    await userEvent.click(screen.getByRole('button', { name: /^Like this video along with/ }))
    const prompt = screen.getByRole('dialog', { name: 'Like this video?' })
    expect(prompt).toHaveTextContent('Sign in to make your opinion count.')
    expect(within(prompt).getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')

    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'Like this video?' })).not.toBeInTheDocument()
  })

  it('puts Up next under the description on narrow screens', async () => {
    setScreenWidth(900)
    await openWatch()
    const upNext = await screen.findByRole('region', { name: 'Up next' })
    const comments = screen.getByRole('region', { name: /Comments/ })
    expect(upNext.compareDocumentPosition(comments)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  })

  it('says the video is unavailable for an unknown id', async () => {
    renderApp('/watch?v=nope')
    expect(await screen.findByText('Video unavailable')).toBeInTheDocument()
  })
})
