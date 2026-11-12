import { type SyntheticEvent, useEffect, useEffectEvent, useRef, useState } from 'react'

import Icon, { type IconName } from '../components/Icon'
import { formatDuration } from '../lib/format'
import ControlButton from './ControlButton'
import styles from './Player.module.css'
import ProgressBar from './ProgressBar'
import { clamp, loadVolume, saveVolume, SPEEDS } from './settings'
import SpeedMenu from './SpeedMenu'
import { useMediaState } from './useMediaState'
import VolumeControl from './VolumeControl'

interface PlayerProps {
  src: string
  poster: string
  /** Seconds to start at; read once, when the player mounts. */
  startAt?: number
  theater: boolean
  onTheaterToggle: () => void
  /** Shows the Next button (Shift+N). */
  onNext?: () => void
  /** The video played to the end. */
  onEnded?: () => void
  /** Called while the video plays, with the seconds played so far. Skipped parts don't count. */
  onPlayed?: (seconds: number) => void
  /** Where playback is: as it plays, and `urgent` on start, pause and end. */
  onPosition?: (seconds: number, urgent: boolean) => void
}

/** The icon or text that flashes in the middle after an action. */
interface Feedback {
  id: number
  icon?: IconName
  text?: string
}

const IDLE_MS = 3000

/** Typing in fields, menus and dialogs is not a player shortcut. */
function isShortcut(event: KeyboardEvent): boolean {
  if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return false
  const target = event.target as Element
  return !target.closest('input, textarea, select, [contenteditable="true"], [role="menu"], dialog')
}

/** Total length of the played ranges: seeking forward adds nothing, replaying a part adds it once. */
function playedSeconds(played: TimeRanges): number {
  let total = 0
  for (let i = 0; i < played.length; i++) total += played.end(i) - played.start(i)
  return total
}

/** YouTube-like controls over a native <video>: the browser does the loading and decoding. */
export default function Player({
  src,
  poster,
  startAt,
  theater,
  onTheaterToggle,
  onNext,
  onEnded,
  onPlayed,
  onPosition,
}: PlayerProps) {
  const root = useRef<HTMLDivElement>(null)
  const video = useRef<HTMLVideoElement>(null)
  const media = useMediaState(video)
  // Kept from the mount: a later startAt would change src and reload the video.
  const [start] = useState(startAt)
  const [fullscreen, setFullscreen] = useState(false)
  const [active, setActive] = useState(true)
  const [menuOpen, setMenuOpen] = useState(false)
  const [feedback, setFeedback] = useState<Feedback | null>(null)
  const idleTimer = useRef(0)
  const feedbackId = useRef(0)

  const controlsShown = media.paused || active || menuOpen || media.error

  // Restore the volume and try to autoplay, as YouTube does; if the browser refuses, it stays paused.
  useEffect(() => {
    const element = video.current!
    const saved = loadVolume()
    if (saved) {
      element.volume = saved.volume
      element.muted = saved.muted
    }
    element.play().catch(() => {})
    idleTimer.current = window.setTimeout(() => setActive(false), IDLE_MS)
    return () => window.clearTimeout(idleTimer.current)
  }, [])

  useEffect(() => {
    const onChange = () => setFullscreen(document.fullscreenElement === root.current)
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

  /** Pointer or keyboard use shows the controls; they hide again after a pause in activity. */
  function wake() {
    setActive(true)
    window.clearTimeout(idleTimer.current)
    idleTimer.current = window.setTimeout(() => setActive(false), IDLE_MS)
  }

  function flash(next: Omit<Feedback, 'id'>) {
    feedbackId.current += 1
    setFeedback({ ...next, id: feedbackId.current })
  }

  function togglePlay() {
    const element = video.current!
    if (element.paused || element.ended) {
      element.play().catch(() => {})
      flash({ icon: 'play' })
    } else {
      element.pause()
      flash({ icon: 'pause' })
    }
  }

  function seekTo(time: number) {
    const element = video.current!
    const end = Number.isFinite(element.duration) ? element.duration : 0
    element.currentTime = clamp(time, 0, end)
  }

  function seekBy(seconds: number) {
    seekTo(video.current!.currentTime + seconds)
    flash({ text: seconds < 0 ? `« ${-seconds} seconds` : `${seconds} seconds »` })
  }

  function changeVolume(volume: number, show = false) {
    const element = video.current!
    element.volume = clamp(volume, 0, 1)
    element.muted = element.volume === 0
    saveVolume({ volume: element.volume, muted: element.muted })
    if (show) flash({ text: `${Math.round(element.volume * 100)}%` })
  }

  function toggleMute(show = false) {
    const element = video.current!
    if (element.muted || element.volume === 0) {
      element.muted = false
      // Unmuting at zero would stay silent: bring back an audible level, as YouTube does.
      if (element.volume === 0) element.volume = 0.5
    } else {
      element.muted = true
    }
    saveVolume({ volume: element.volume, muted: element.muted })
    if (show) flash({ icon: element.muted ? 'volumeOff' : 'volumeUp' })
  }

  function reportPlayed(event: SyntheticEvent<HTMLVideoElement>) {
    const element = event.currentTarget
    if (onPlayed && !element.paused) onPlayed(playedSeconds(element.played))
  }

  function reportPosition(event: SyntheticEvent<HTMLVideoElement>, urgent: boolean) {
    onPosition?.(event.currentTarget.currentTime, urgent)
  }

  function changeRate(rate: number) {
    video.current!.playbackRate = rate
  }

  function stepRate(direction: -1 | 1) {
    const index = SPEEDS.indexOf(media.rate)
    const next =
      SPEEDS[clamp((index < 0 ? SPEEDS.indexOf(1) : index) + direction, 0, SPEEDS.length - 1)]
    changeRate(next)
    flash({ text: `${next}x` })
  }

  function toggleFullscreen() {
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {})
    else root.current?.requestFullscreen?.().catch(() => {})
  }

  const onKeyDown = useEffectEvent((event: KeyboardEvent) => {
    if (!isShortcut(event)) return
    const target = event.target as Element
    const inPlayer = root.current?.contains(target) ?? false
    const key = event.key.length === 1 && !event.shiftKey ? event.key.toLowerCase() : event.key
    switch (key) {
      case ' ':
        // Space on a button presses the button.
        if (target.closest('button, a')) return
        togglePlay()
        break
      case 'k':
        togglePlay()
        break
      case 'j':
        seekBy(-10)
        break
      case 'l':
        seekBy(10)
        break
      case 'ArrowLeft':
        seekBy(-5)
        break
      case 'ArrowRight':
        seekBy(5)
        break
      // Up/Down and Home/End scroll the page unless the player has focus.
      case 'ArrowUp':
      case 'ArrowDown':
        if (!inPlayer) return
        changeVolume((media.muted ? 0 : media.volume) + (key === 'ArrowUp' ? 0.05 : -0.05), true)
        break
      case 'Home':
      case 'End':
        if (!inPlayer) return
        seekTo(key === 'Home' ? 0 : media.duration)
        break
      case 'm':
        toggleMute(true)
        break
      case 'f':
        toggleFullscreen()
        break
      case 't':
        if (fullscreen) return
        onTheaterToggle()
        break
      case '<':
        stepRate(-1)
        break
      case '>':
        stepRate(1)
        break
      case 'N':
        if (!onNext) return
        onNext()
        break
      default:
        if (!/^\d$/.test(key)) return
        seekTo((media.duration * Number(key)) / 10)
    }
    event.preventDefault()
    wake()
  })

  useEffect(() => {
    const listener = (event: KeyboardEvent) => onKeyDown(event)
    document.addEventListener('keydown', listener)
    return () => document.removeEventListener('keydown', listener)
  }, [])

  return (
    <div
      ref={root}
      className={controlsShown ? styles.player : `${styles.player} ${styles.idle}`}
      role="region"
      aria-label="Video player"
      onPointerMove={wake}
      onPointerLeave={() => setActive(false)}
      onFocus={wake}
    >
      <video
        ref={video}
        className={styles.video}
        src={start ? `${src}#t=${start}` : src} // a media fragment: the browser starts there
        poster={poster}
        preload="metadata"
        playsInline
        onClick={togglePlay}
        onDoubleClick={toggleFullscreen}
        onPlaying={(event) => {
          reportPlayed(event)
          reportPosition(event, true)
        }}
        onTimeUpdate={(event) => {
          reportPlayed(event)
          reportPosition(event, false)
        }}
        onPause={(event) => reportPosition(event, true)}
        onEnded={(event) => {
          reportPosition(event, true)
          onEnded?.()
        }}
      />

      {media.waiting && !media.error && (
        <div className={styles.buffering} role="status" aria-label="Loading video" />
      )}

      {feedback && (
        <div
          key={feedback.id}
          className={feedback.icon ? styles.feedbackIcon : styles.feedbackText}
          aria-hidden="true"
          onAnimationEnd={() => setFeedback(null)}
        >
          {feedback.icon ? <Icon name={feedback.icon} size={36} /> : feedback.text}
        </div>
      )}

      {media.error && (
        <div className={styles.error} role="alert">
          <Icon name="error" size={48} />
          <p className={styles.errorTitle}>Can’t play this video</p>
          <p className={styles.errorHint}>The video file didn’t load. Try again later.</p>
        </div>
      )}

      <div className={styles.chrome}>
        <ProgressBar
          currentTime={media.currentTime}
          duration={media.duration}
          buffered={media.buffered}
          onSeek={seekTo}
        />
        <div className={styles.bar}>
          <div className={styles.left}>
            <ControlButton
              icon={media.ended ? 'replay' : media.paused ? 'play' : 'pause'}
              label={media.ended ? 'Replay' : media.paused ? 'Play' : 'Pause'}
              iconSize={36}
              shortcut="k"
              onClick={togglePlay}
            />
            {onNext && (
              <ControlButton
                icon="next"
                label="Next"
                shortcut="Shift+N"
                iconSize={32}
                onClick={onNext}
              />
            )}
            <VolumeControl
              volume={media.volume}
              muted={media.muted}
              onToggleMute={() => toggleMute()}
              onChange={(volume) => changeVolume(volume)}
            />
            <span className={styles.time}>
              {formatDuration(media.currentTime)} / {formatDuration(media.duration)}
            </span>
          </div>
          <div className={styles.right}>
            <SpeedMenu
              rate={media.rate}
              open={menuOpen}
              onOpenChange={setMenuOpen}
              onChange={changeRate}
            />
            {!fullscreen && (
              <ControlButton
                icon={theater ? 'defaultView' : 'theater'}
                label={theater ? 'Default view' : 'Theater mode'}
                iconSize={36}
                shortcut="t"
                onClick={onTheaterToggle}
              />
            )}
            <ControlButton
              icon={fullscreen ? 'fullscreenExit' : 'fullscreen'}
              label={fullscreen ? 'Exit full screen' : 'Full screen'}
              shortcut="f"
              onClick={toggleFullscreen}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
