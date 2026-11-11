import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { loadMetadata } from '../test/media'
import Player from './Player'

interface Callbacks {
  onTheaterToggle?: () => void
  onNext?: () => void
  onPlayed?: (seconds: number) => void
}

function renderPlayer(props: Callbacks = {}) {
  const view = render(
    <>
      <input aria-label="Comment" />
      <Player
        src="/demo-data/videos/sintel-trailer.mp4"
        poster="/demo-data/thumbnails/sintel-trailer-7.jpg"
        theater={false}
        onTheaterToggle={props.onTheaterToggle ?? (() => {})}
        onNext={props.onNext}
        onPlayed={props.onPlayed}
      />
    </>,
  )
  const video = view.container.querySelector('video')!
  act(() => loadMetadata(video, 52))
  return video
}

describe('Player', () => {
  afterEach(() => localStorage.clear())

  it('autoplays and toggles with the button, k and space', async () => {
    const video = renderPlayer()
    expect(video.paused).toBe(false)

    await userEvent.click(screen.getByRole('button', { name: 'Pause' }))
    expect(video.paused).toBe(true)

    await userEvent.keyboard('k')
    expect(video.paused).toBe(false)
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument()

    await userEvent.keyboard(' ')
    expect(video.paused).toBe(true)
  })

  it('seeks with j/l, arrows and number keys, within the video', async () => {
    const video = renderPlayer()
    await userEvent.keyboard('l')
    expect(video.currentTime).toBe(10)
    await userEvent.keyboard('{ArrowRight}')
    expect(video.currentTime).toBe(15)
    await userEvent.keyboard('j')
    expect(video.currentTime).toBe(5)
    await userEvent.keyboard('jj')
    expect(video.currentTime).toBe(0)
    await userEvent.keyboard('5')
    expect(video.currentTime).toBe(26)
    expect(screen.getByRole('slider', { name: 'Seek slider' })).toHaveAttribute(
      'aria-valuetext',
      '0:26 of 0:52',
    )
  })

  it('ignores shortcuts typed into a field', async () => {
    const video = renderPlayer()
    await userEvent.type(screen.getByRole('textbox', { name: 'Comment' }), 'kl m')
    expect(video.paused).toBe(false)
    expect(video.currentTime).toBe(0)
    expect(video.muted).toBe(false)
  })

  it('mutes with m and remembers the volume for the next video', async () => {
    const video = renderPlayer()
    await userEvent.keyboard('m')
    expect(video.muted).toBe(true)
    expect(screen.getByRole('slider', { name: 'Volume' })).toHaveAttribute('aria-valuenow', '0')

    await userEvent.click(screen.getByRole('button', { name: 'Unmute' }))
    expect(video.muted).toBe(false)

    screen.getByRole('slider', { name: 'Volume' }).focus()
    await userEvent.keyboard('{ArrowLeft}{ArrowLeft}')
    expect(video.volume).toBeCloseTo(0.9)
    expect(video.currentTime).toBe(0) // the slider keeps the arrows
    expect(JSON.parse(localStorage.getItem('vitube:volume')!)).toMatchObject({ muted: false })
  })

  it('asks the page for theater mode and the next video', async () => {
    const onTheaterToggle = vi.fn()
    const onNext = vi.fn()
    renderPlayer({ onTheaterToggle, onNext })

    await userEvent.keyboard('t')
    await userEvent.click(screen.getByRole('button', { name: 'Theater mode' }))
    expect(onTheaterToggle).toHaveBeenCalledTimes(2)

    await userEvent.keyboard('{Shift>}N{/Shift}')
    expect(onNext).toHaveBeenCalledOnce()
  })

  it('changes the playback speed from the settings menu', async () => {
    const video = renderPlayer()
    await userEvent.click(screen.getByRole('button', { name: 'Settings' }))
    await userEvent.click(screen.getByRole('menuitem', { name: /Playback speed\s*Normal/ }))
    await userEvent.click(screen.getByRole('menuitemradio', { name: '1.5' }))

    expect(video.playbackRate).toBe(1.5)
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    await userEvent.keyboard('>')
    expect(video.playbackRate).toBe(1.75)
  })

  it('says when the file fails to load', () => {
    const video = renderPlayer()
    act(() => {
      fireEvent.error(video)
    })
    expect(screen.getByRole('alert')).toHaveTextContent('Can’t play this video')
  })

  it('reports the seconds played, not the seconds skipped, while playing', async () => {
    const onPlayed = vi.fn()
    const video = renderPlayer({ onPlayed })
    // Played 0–10 s, skipped to 40 s, played 40–45 s.
    const played = [
      [0, 10],
      [40, 45],
    ]
    Object.defineProperty(video, 'played', {
      value: { length: 2, start: (i: number) => played[i][0], end: (i: number) => played[i][1] },
    })

    fireEvent.timeUpdate(video)
    expect(onPlayed).toHaveBeenLastCalledWith(15)

    await userEvent.click(screen.getByRole('button', { name: 'Pause' }))
    onPlayed.mockClear()
    fireEvent.timeUpdate(video)
    expect(onPlayed).not.toHaveBeenCalled()
  })
})
