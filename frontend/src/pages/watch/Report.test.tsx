import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ANNA, json, mockApi } from '../../test/api'
import { renderApp } from '../../test/render'
import { comment, detail, page, summary } from '../../test/videos'
import type { Video } from '../../videos/types'

const VIDEO = detail(1, { title: 'Fake giveaway' })
const OWN = { handle: ANNA.handle, name: ANNA.handle, avatar_url: null }
const SIGNED_IN = { 'GET /api/auth/me': () => json(200, ANNA) }
const GUEST = { 'GET /api/auth/me': () => json(401, { detail: 'Sign in required' }) }
const COMMENT = comment(1, { text: 'Buy followers at example.com' })

/** One watch page; reports answer 204 unless `reportStatus` says otherwise. */
function mockWatch(
  video: Video = VIDEO,
  viewer = SIGNED_IN,
  comments = [COMMENT],
  reportStatus = 204,
) {
  const base = `/api/videos/${video.id}`
  const answer = () =>
    reportStatus === 204 ? json(204) : json(reportStatus, { detail: 'Too many reports, try later' })
  return mockApi({
    ...viewer,
    [`GET ${base}`]: () => json(200, video),
    [`GET ${base}/related`]: () => json(200, page([summary(2)])),
    [`GET ${base}/comments`]: () => json(200, page(comments)),
    [`POST ${base}/views/start`]: () => json(204),
    [`POST ${base}/report`]: answer,
    [`POST /api/comments/${COMMENT.id}/report`]: answer,
  })
}

async function openWatch(video: Video = VIDEO) {
  renderApp(`/watch?v=${video.id}`)
  await screen.findByRole('heading', { level: 1, name: video.title })
}

const sentReports = async (fetch: ReturnType<typeof mockApi>) =>
  Promise.all(
    fetch.mock.calls
      .map(([request]) => request)
      .filter((request) => request.url.endsWith('/report'))
      .map(async (request) => [new URL(request.url).pathname, await request.clone().json()]),
  )

/** The comments; Up next cards have a ⋮ of their own. */
const comments = () => screen.getByRole('region', { name: /Comments?$/ })

async function commentMenu() {
  const section = await screen.findByRole('region', { name: /Comments?$/ })
  return within(section).findByRole('button', { name: 'Action menu' })
}

describe('reporting from the watch page', () => {
  it('reports a video: a reason, then optional details, then thanks', async () => {
    const fetch = mockWatch()
    await openWatch()

    await userEvent.click(screen.getByRole('button', { name: 'More actions' }))
    await userEvent.click(screen.getByRole('menuitem', { name: 'Report' }))
    const dialog = screen.getByRole('dialog', { name: 'Report video' })
    const next = within(dialog).getByRole('button', { name: 'Next' })
    expect(next).toBeDisabled()

    await userEvent.click(within(dialog).getByLabelText('Spam or misleading'))
    await userEvent.click(next)
    await userEvent.type(within(dialog).getByRole('textbox'), 'Asks for card details')
    expect(dialog).toHaveTextContent('21/500')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Report' }))

    expect(await within(dialog).findByText('Thanks for reporting')).toBeInTheDocument()
    expect(await sentReports(fetch)).toEqual([
      ['/api/videos/video-00001/report', { reason: 'spam', details: 'Asks for card details' }],
    ])
    await userEvent.click(within(dialog).getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('dialog', { name: 'Report video' })).not.toBeInTheDocument()
  })

  it('goes back to the reasons with the choice kept', async () => {
    mockWatch()
    await openWatch()
    await userEvent.click(screen.getByRole('button', { name: 'More actions' }))
    await userEvent.click(screen.getByRole('menuitem', { name: 'Report' }))
    const dialog = screen.getByRole('dialog', { name: 'Report video' })

    await userEvent.click(within(dialog).getByLabelText('Harassment or bullying'))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Next' }))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Back' }))

    expect(within(dialog).getByLabelText('Harassment or bullying')).toBeChecked()
  })

  it('reports a comment from its menu, without the details step', async () => {
    const fetch = mockWatch()
    await openWatch()

    await userEvent.click(await commentMenu())
    await userEvent.click(screen.getByRole('menuitem', { name: 'Report' }))
    const dialog = screen.getByRole('dialog', { name: 'Report comment' })
    await userEvent.click(within(dialog).getByLabelText('Spam or misleading'))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Report' }))

    expect(await within(dialog).findByText('Thanks for reporting')).toBeInTheDocument()
    expect(await sentReports(fetch)).toEqual([
      [`/api/comments/${COMMENT.id}/report`, { reason: 'spam', details: '' }],
    ])
  })

  it('says why a report failed and keeps the dialog open', async () => {
    mockWatch(VIDEO, SIGNED_IN, [COMMENT], 429)
    await openWatch()
    await userEvent.click(await commentMenu())
    await userEvent.click(screen.getByRole('menuitem', { name: 'Report' }))
    const dialog = screen.getByRole('dialog', { name: 'Report comment' })

    await userEvent.click(within(dialog).getByLabelText('Child abuse'))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Report' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'Too many reports, try later',
    )
    expect(within(dialog).getByLabelText('Child abuse')).toBeChecked()
  })

  it('offers no report on the viewer’s own video and comments', async () => {
    const own = detail(1, { title: 'My trip', channel: OWN })
    mockWatch(own, SIGNED_IN, [comment(1, { author: OWN })])
    await openWatch(own)

    await screen.findByText('Comment 1')
    expect(screen.queryByRole('button', { name: 'More actions' })).not.toBeInTheDocument()
    expect(
      within(comments()).queryByRole('button', { name: 'Action menu' }),
    ).not.toBeInTheDocument()
  })

  it('asks a guest to sign in', async () => {
    mockWatch(VIDEO, GUEST)
    await openWatch()

    await userEvent.click(screen.getByRole('button', { name: 'More actions' }))

    const card = screen.getByRole('dialog', { name: 'Need to report the video?' })
    expect(card).toHaveTextContent('Sign in to report inappropriate content.')
    expect(within(card).getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
  })
})

describe('a restricted video', () => {
  it('shows its owner a hidden video frozen, with the reason', async () => {
    const hidden = detail(1, { title: 'My trip', channel: OWN, is_hidden: true })
    const fetch = mockWatch(hidden)
    await openWatch(hidden)

    const notice = screen.getByRole('note')
    expect(notice).toHaveTextContent('Hidden by a moderator')
    expect(notice).toHaveTextContent('Only the channel owner and moderators can see this video.')
    expect(screen.getByRole('link', { name: ANNA.handle })).toBeInTheDocument()
    for (const name of [/Like this video/, 'Share', 'More actions']) {
      expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
    }
    // No comments, and playback makes no view.
    expect(screen.getByText('Comments are turned off.')).toBeInTheDocument()
    await screen.findByRole('region', { name: 'Up next' })
    const paths = fetch.mock.calls.map(([request]) => new URL(request.url).pathname)
    expect(paths.filter((path) => path.includes('/comments') || path.includes('/views'))).toEqual(
      [],
    )
  })

  it('tells a moderator a terminated channel’s video is frozen', async () => {
    mockWatch(detail(1, { title: 'Scam', channel_terminated: true }), {
      'GET /api/auth/me': () => json(200, { ...ANNA, role: 'moderator' }),
    })
    await openWatch(detail(1, { title: 'Scam' }))

    expect(screen.getByRole('note')).toHaveTextContent('Channel terminated')
    expect(screen.queryByRole('button', { name: 'More actions' })).not.toBeInTheDocument()
  })
})
