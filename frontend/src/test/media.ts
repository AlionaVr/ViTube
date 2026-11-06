// jsdom has no media playback. These stubs flip the state and fire the events a browser would.

type MediaWithState = HTMLMediaElement & { _paused?: boolean }

export function installMediaStubs() {
  const proto = HTMLMediaElement.prototype as MediaWithState

  Object.defineProperty(proto, 'paused', {
    configurable: true,
    get(this: MediaWithState) {
      return this._paused ?? true
    },
  })
  proto.play = function (this: MediaWithState) {
    this._paused = false
    this.dispatchEvent(new Event('play'))
    this.dispatchEvent(new Event('playing'))
    return Promise.resolve()
  }
  proto.pause = function (this: MediaWithState) {
    this._paused = true
    this.dispatchEvent(new Event('pause'))
  }
  proto.load = () => {}

  const events: [prop: string, event: string][] = [
    ['currentTime', 'timeupdate'],
    ['volume', 'volumechange'],
    ['muted', 'volumechange'],
    ['playbackRate', 'ratechange'],
  ]
  for (const [prop, event] of events) {
    const own = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, prop)!
    Object.defineProperty(proto, prop, {
      ...own,
      set(this: HTMLMediaElement, value: unknown) {
        own.set!.call(this, value)
        this.dispatchEvent(new Event(event))
      },
    })
  }
}

/** Pretend the video has loaded its metadata. */
export function loadMetadata(video: HTMLVideoElement, duration: number) {
  Object.defineProperty(video, 'duration', { configurable: true, value: duration })
  video.dispatchEvent(new Event('loadedmetadata'))
  video.dispatchEvent(new Event('durationchange'))
}
