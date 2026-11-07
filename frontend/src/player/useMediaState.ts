import { type RefObject, useEffect, useState } from 'react'

export interface MediaState {
  paused: boolean
  ended: boolean
  /** Playback stalls for data (or a seek waits for it). */
  waiting: boolean
  error: boolean
  currentTime: number
  duration: number
  /** End of the buffered range around the playhead. */
  buffered: number
  volume: number
  muted: boolean
  rate: number
}

const INITIAL: MediaState = {
  paused: true,
  ended: false,
  waiting: false,
  error: false,
  currentTime: 0,
  duration: 0,
  buffered: 0,
  volume: 1,
  muted: false,
  rate: 1,
}

function bufferedEnd(video: HTMLVideoElement): number {
  const { buffered, currentTime } = video
  for (let i = 0; i < buffered.length; i++) {
    if (buffered.start(i) <= currentTime && currentTime <= buffered.end(i)) return buffered.end(i)
  }
  return 0
}

const READ_ON = [
  'play',
  'pause',
  'ended',
  'timeupdate',
  'durationchange',
  'loadedmetadata',
  'progress',
  'volumechange',
  'ratechange',
  'seeked',
]

/** The <video> element's state as React state, updated from its own events. */
export function useMediaState(ref: RefObject<HTMLVideoElement | null>): MediaState {
  const [state, setState] = useState(INITIAL)

  useEffect(() => {
    const video = ref.current
    if (!video) return
    const read = () =>
      setState((previous) => {
        const next: MediaState = {
          ...previous,
          paused: video.paused,
          ended: video.ended,
          currentTime: video.currentTime,
          duration: Number.isFinite(video.duration) ? video.duration : 0,
          buffered: bufferedEnd(video),
          volume: video.volume,
          muted: video.muted,
          rate: video.playbackRate,
        }
        // Same object back = no re-render, which matters for the frame loop below.
        const keys = Object.keys(next) as (keyof MediaState)[]
        return keys.every((key) => next[key] === previous[key]) ? previous : next
      })
    const waiting = (value: boolean) => () =>
      setState((previous) => ({ ...previous, waiting: value }))
    const onWaiting = waiting(true)
    const onReady = waiting(false)
    const onError = () => setState((previous) => ({ ...previous, error: true, waiting: false }))

    // timeupdate fires ~4 times a second; a frame loop keeps the progress bar smooth while playing.
    let frame = 0
    const tick = () => {
      read()
      frame = requestAnimationFrame(tick)
    }
    const onPlay = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(tick)
    }
    const onStop = () => cancelAnimationFrame(frame)

    for (const event of READ_ON) video.addEventListener(event, read)
    video.addEventListener('waiting', onWaiting)
    video.addEventListener('seeking', onWaiting)
    for (const event of ['playing', 'canplay', 'seeked']) video.addEventListener(event, onReady)
    video.addEventListener('error', onError)
    video.addEventListener('play', onPlay)
    video.addEventListener('pause', onStop)
    video.addEventListener('ended', onStop)

    return () => {
      cancelAnimationFrame(frame)
      for (const event of READ_ON) video.removeEventListener(event, read)
      video.removeEventListener('waiting', onWaiting)
      video.removeEventListener('seeking', onWaiting)
      for (const event of ['playing', 'canplay', 'seeked'])
        video.removeEventListener(event, onReady)
      video.removeEventListener('error', onError)
      video.removeEventListener('play', onPlay)
      video.removeEventListener('pause', onStop)
      video.removeEventListener('ended', onStop)
    }
  }, [ref])

  return state
}
