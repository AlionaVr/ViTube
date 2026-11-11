import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ANNA, json, mockApi } from '../../../test/api'
import { renderApp } from '../../../test/render'
import { comment, detail, page, summary } from '../../../test/videos'

const VIDEO = detail(1, { title: 'Sintel – trailer' })
const THREAD = comment(1, { reply_count: 1 })
const REPLY = comment(2, {
  author: { handle: 'dragonfan', name: 'Dragon fan', avatar_url: null },
  text: 'Same here',
})

/** A watch page with one thread; posted replies are kept to inspect. */
function mockWatch() {
  const base = `/api/videos/${VIDEO.id}`
  const posted: unknown[] = []
  mockApi({
    'GET /api/auth/me': () => json(200, ANNA),
    [`GET ${base}`]: () => json(200, VIDEO),
    [`GET ${base}/related`]: () => json(200, page([summary(2)])),
    [`GET ${base}/comments`]: () => json(200, page([THREAD])),
    [`GET /api/comments/${THREAD.id}/replies`]: () => json(200, page([REPLY])),
    [`POST ${base}/views/start`]: () => json(204),
    [`POST ${base}/comments`]: async (request) => {
      const body = (await request.json()) as { text: string }
      posted.push(body)
      return json(201, comment(3, { text: body.text }))
    },
  })
  return posted
}

describe('replying to a comment', () => {
  it('starts the reply with the @handle it answers, typing after it', async () => {
    const posted = mockWatch()
    renderApp(`/watch?v=${VIDEO.id}`)

    const thread = (await screen.findByText('Comment 1')).closest('article')!
    await userEvent.click(within(thread).getByRole('button', { name: 'Reply' }))
    const box = within(thread).getByRole('textbox', { name: 'Add a reply…' })
    expect(box).toHaveValue('@framebyframe ')
    expect(box).toHaveFocus()

    await userEvent.keyboard('Thanks!')
    // The toolbar's Reply opened the box; the box's own Reply sends it.
    await userEvent.click(within(thread).getAllByRole('button', { name: 'Reply' }).at(-1)!)

    await waitFor(() =>
      expect(posted).toEqual([{ text: '@framebyframe Thanks!', parent_id: THREAD.id }]),
    )
  })

  it('answers a reply in its thread, naming the reply’s author', async () => {
    const posted = mockWatch()
    renderApp(`/watch?v=${VIDEO.id}`)
    await userEvent.click(await screen.findByRole('button', { name: '1 reply' }))

    const reply = (await screen.findByText('Same here')).closest('article')!
    await userEvent.click(within(reply).getByRole('button', { name: 'Reply' }))
    await userEvent.keyboard('Me too')
    await userEvent.click(within(reply).getAllByRole('button', { name: 'Reply' }).at(-1)!)

    await waitFor(() =>
      expect(posted).toEqual([{ text: '@dragonfan Me too', parent_id: THREAD.id }]),
    )
  })
})
