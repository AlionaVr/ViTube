import { useState } from 'react'

import Dialog from '../components/Dialog'
import Icon from '../components/Icon'
import SignInGate from '../components/SignInGate'
import buttons from '../styles/buttons.module.css'
import { useSetSubscribed } from './hooks'
import styles from './SubscribeButton.module.css'
import type { Channel } from './types'

type Props = { channel: Pick<Channel, 'handle' | 'name' | 'is_subscribed'> }

/** Subscribe, or Subscribed with a confirm dialog to unsubscribe. Not for the viewer's own channel. */
export default function SubscribeButton({ channel }: Props) {
  const setSubscribed = useSetSubscribed(channel.handle)
  const [confirming, setConfirming] = useState(false)

  if (channel.is_subscribed) {
    return (
      <>
        <button
          type="button"
          className={`${buttons.pill} ${buttons.tonal} ${buttons.iconLeading} ${buttons.iconTrailing}`}
          aria-haspopup="dialog"
          onClick={() => setConfirming(true)}
        >
          <Icon name="notifications" />
          Subscribed
          <Icon name="chevronDown" />
        </button>
        <Dialog open={confirming} onClose={() => setConfirming(false)} label="Unsubscribe">
          <p className={styles.confirm}>Unsubscribe from {channel.name}?</p>
          <div className={styles.confirmActions}>
            <button
              type="button"
              className={`${buttons.pill} ${buttons.text}`}
              onClick={() => setConfirming(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              className={`${buttons.pill} ${buttons.link}`}
              onClick={() => {
                setSubscribed.mutate(false)
                setConfirming(false)
              }}
            >
              Unsubscribe
            </button>
          </div>
        </Dialog>
      </>
    )
  }

  return (
    <SignInGate
      title="Want to subscribe to this channel?"
      text="Sign in to subscribe to this channel."
      onAction={() => setSubscribed.mutate(true)}
    >
      {(props) => (
        <button type="button" className={`${buttons.pill} ${buttons.filled}`} {...props}>
          Subscribe
        </button>
      )}
    </SignInGate>
  )
}
