import { type KeyboardEvent, type PointerEvent, useRef } from 'react'

import ControlButton from './ControlButton'
import styles from './Player.module.css'
import { clamp } from './settings'

interface VolumeControlProps {
  volume: number
  muted: boolean
  onToggleMute: () => void
  onChange: (volume: number) => void
}

/** Mute button; the slider slides out on hover or focus, as on YouTube. */
export default function VolumeControl({
  volume,
  muted,
  onToggleMute,
  onChange,
}: VolumeControlProps) {
  const slider = useRef<HTMLDivElement>(null)
  const level = muted ? 0 : volume
  const icon = level === 0 ? 'volumeOff' : level < 0.5 ? 'volumeDown' : 'volumeUp'

  function setFromPointer(event: PointerEvent) {
    const rect = slider.current!.getBoundingClientRect()
    if (rect.width > 0) onChange(clamp((event.clientX - rect.left) / rect.width, 0, 1))
  }

  function handleKeyDown(event: KeyboardEvent) {
    const step = { ArrowRight: 0.05, ArrowUp: 0.05, ArrowLeft: -0.05, ArrowDown: -0.05 }[event.key]
    if (step === undefined) return
    // The slider owns the arrows while focused, so the player doesn't seek.
    event.preventDefault()
    event.stopPropagation()
    onChange(clamp(level + step, 0, 1))
  }

  return (
    <div className={styles.volume}>
      <ControlButton
        icon={icon}
        label={level === 0 ? 'Unmute' : 'Mute'}
        iconSize={32}
        shortcut="m"
        onClick={onToggleMute}
      />
      <div
        ref={slider}
        className={styles.volumeSlider}
        role="slider"
        tabIndex={0}
        aria-label="Volume"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(level * 100)}
        onKeyDown={handleKeyDown}
        onPointerDown={(event) => {
          event.currentTarget.setPointerCapture?.(event.pointerId)
          setFromPointer(event)
        }}
        onPointerMove={(event) => {
          if (event.buttons === 1) setFromPointer(event)
        }}
      >
        <div className={styles.volumeTrack}>
          <div className={styles.volumeLevel} style={{ width: `${level * 100}%` }} />
        </div>
        <div
          className={styles.volumeHandle}
          style={{ left: `calc(6px + ${level} * (100% - 12px))` }}
        />
      </div>
    </div>
  )
}
