import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { loadMetadata } from '../test/media'
import type { UpNextVideo } from './AutoplayCountdown'
import Player from './Player'

interface Callbacks {
  onTheaterToggle?: () => void
  onNext?: () => void
  onEnded?: () => void
  onPlayed?: (seconds: number) => void
  autoplay?: boolean
  onAutoplayToggle?: () => void
  upNext?: UpNextVideo
}

const NEXT: UpNextVideo = { title: 'Sintel', channel: 'Open Movie Club', thumbnail: null }

function renderPlayer(props: Callbacks = {}) {
  const view = render(
    <>
      <input aria-label="Comment" />
      <Player
        src="/media/videos/0193/720p.mp4"
        poster="/media/thumbs/0193.jpg"
        theater={false}
        onTheaterToggle={props.onTheaterToggle ?? (() => {})}
        onNext={props.onNext}
        onEnded={props.onEnded}
        onPlayed={props.onPlayed}
        autoplay={props.autoplay}
        onAutoplayToggle={props.onAutoplayToggle}
        upNext={props.upNext}
      />
    </>,
  )
  const video = view.container.querySelector('video')!
  act(() => loadMetadata(video, 52))
  return video
}

/** Plays to the end, as a browser reports it: pause, then ended. */
function playToTheEnd(video: HTMLVideoElement) {
  Object.defineProperty(video, 'ended', { configurable: true, value: true })
  act(() => {
    video.pause()
    fireEvent.ended(video)
  })
}

describe('Player', () => {
  afterEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

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

  it('shows a big Play button and no controls while the browser refuses autoplay', async () => {
    vi.spyOn(HTMLMediaElement.prototype, 'play').mockRejectedValueOnce(
      new DOMException('Autoplay is not allowed', 'NotAllowedError'),
    )
    const video = renderPlayer()
    expect(video.paused).toBe(true)
    expect(screen.queryByRole('button', { name: 'Settings' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Play' }))

    expect(video.paused).toBe(false)
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Settings' })).toBeInTheDocument()
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

  it('tells the page when the video ends', () => {
    const onEnded = vi.fn()
    const video = renderPlayer({ onEnded })

    fireEvent.ended(video)

    expect(onEnded).toHaveBeenCalledOnce()
  })

  it('shows the Autoplay switch and asks the page to flip it', async () => {
    const onAutoplayToggle = vi.fn()
    renderPlayer({ autoplay: true, onAutoplayToggle })
    const toggle = screen.getByRole('switch', { name: 'Autoplay' })
    expect(toggle).toBeChecked()

    await userEvent.click(toggle)

    expect(onAutoplayToggle).toHaveBeenCalledOnce()
  })

  it('counts down to the next video at the end', () => {
    vi.useFakeTimers()
    const onNext = vi.fn()
    const video = renderPlayer({ onNext, upNext: NEXT })

    playToTheEnd(video)
    const countdown = screen.getByRole('region', { name: 'Autoplay countdown' })
    expect(countdown).toHaveTextContent('Up next in 5')
    expect(countdown).toHaveTextContent('Sintel')
    act(() => vi.advanceTimersByTime(4000))
    expect(countdown).toHaveTextContent('Up next in 1')
    expect(onNext).not.toHaveBeenCalled()
    act(() => vi.advanceTimersByTime(1000))

    expect(onNext).toHaveBeenCalledOnce()
  })

  it('stays at the end when the countdown is cancelled, until the next replay ends', () => {
    vi.useFakeTimers()
    const onNext = vi.fn()
    const video = renderPlayer({ onNext, upNext: NEXT })
    playToTheEnd(video)

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    act(() => vi.advanceTimersByTime(10_000))
    expect(onNext).not.toHaveBeenCalled()
    expect(screen.queryByRole('region', { name: 'Autoplay countdown' })).not.toBeInTheDocument()

    Object.defineProperty(video, 'ended', { configurable: true, value: false })
    act(() => void video.play())
    playToTheEnd(video)
    fireEvent.click(screen.getByRole('button', { name: 'Play now' }))
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
