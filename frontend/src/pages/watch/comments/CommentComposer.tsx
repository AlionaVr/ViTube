import { type FormEvent, useState } from 'react'

import { useAddComment } from '../../../comments/hooks'
import Avatar from '../../../components/Avatar'
import Icon from '../../../components/Icon'
import SignInGate from '../../../components/SignInGate'
import buttons from '../../../styles/buttons.module.css'
import { useViewer } from '../../../viewer/useViewer'
import styles from './Comments.module.css'

interface CommentComposerProps {
  videoId: string
  /** Set for a reply: YouTube keeps replies one level deep. */
  parentId?: string | null
  /** Replies open focused, with the buttons shown. */
  autoFocus?: boolean
  onDone?: () => void
}

/** "Add a comment…": the buttons appear on focus; Comment is off until there is text. */
export default function CommentComposer({
  videoId,
  parentId = null,
  autoFocus = false,
  onDone,
}: CommentComposerProps) {
  const viewer = useViewer()
  const add = useAddComment(videoId)
  const [text, setText] = useState('')
  const [active, setActive] = useState(autoFocus)
  const reply = parentId !== null
  const avatarSize = reply ? 24 : 40
  const placeholder = reply ? 'Add a reply…' : 'Add a comment…'

  function finish() {
    setText('')
    setActive(false)
    onDone?.()
  }

  function submit(event?: FormEvent) {
    event?.preventDefault()
    if (!text.trim() || add.isPending) return
    add.mutate({ text, parentId }, { onSuccess: finish })
  }

  if (viewer.status !== 'authenticated') {
    return (
      <div className={reply ? `${styles.composer} ${styles.replyComposer}` : styles.composer}>
        <span className={styles.guestAvatar} style={{ width: avatarSize, height: avatarSize }}>
          <Icon name="account" size={avatarSize} />
        </span>
        <SignInGate
          title="Want to join the conversation?"
          text="Sign in to continue."
          onAction={() => {}}
        >
          {(props) => (
            <button type="button" className={styles.fakeInput} {...props}>
              {placeholder}
            </button>
          )}
        </SignInGate>
      </div>
    )
  }

  return (
    <form
      className={reply ? `${styles.composer} ${styles.replyComposer}` : styles.composer}
      onSubmit={submit}
    >
      <Avatar name={viewer.user.handle} size={avatarSize} />
      <div className={styles.field}>
        <textarea
          className={styles.input}
          rows={1}
          placeholder={placeholder}
          aria-label={placeholder}
          // A reply box opens because the viewer pressed Reply.
          autoFocus={autoFocus}
          value={text}
          onFocus={() => setActive(true)}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) submit()
          }}
        />
        {add.isError && (
          <p className={styles.formError} role="alert">
            Your comment wasn’t posted. Try again.
          </p>
        )}
        {active && (
          <div className={styles.formButtons}>
            <button type="button" className={`${buttons.pill} ${buttons.text}`} onClick={finish}>
              Cancel
            </button>
            <button
              type="submit"
              className={`${buttons.pill} ${buttons.primary}`}
              disabled={!text.trim() || add.isPending}
            >
              {reply ? 'Reply' : 'Comment'}
            </button>
          </div>
        )}
      </div>
    </form>
  )
}
