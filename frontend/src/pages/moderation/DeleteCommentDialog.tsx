import Dialog from '../../components/Dialog'
import type { ModeratedComment } from '../../moderation/api'
import { useDeleteComment } from '../../moderation/hooks'
import buttons from '../../styles/buttons.module.css'
import styles from './ModerationPage.module.css'

/** Deleting can't be undone: asks first. */
export default function DeleteCommentDialog({
  target,
  onClose,
}: {
  target: ModeratedComment | null
  onClose: () => void
}) {
  const remove = useDeleteComment()
  const close = () => {
    remove.reset()
    onClose()
  }
  return (
    <Dialog open={target !== null} onClose={close} label="Delete comment">
      {target && (
        <>
          <h2 className={styles.dialogTitle}>Delete comment?</h2>
          <p className={styles.dialogText}>
            {target.is_reply
              ? 'It disappears for everyone. Its reports will close.'
              : 'It disappears for everyone, with its replies. Its reports will close.'}
          </p>
          {remove.isError && (
            <p className={styles.error} role="alert">
              {remove.error.message}
            </p>
          )}
          <div className={styles.dialogActions}>
            <button type="button" className={`${buttons.pill} ${buttons.text}`} onClick={close}>
              Cancel
            </button>
            <button
              type="button"
              className={`${buttons.pill} ${buttons.link}`}
              disabled={remove.isPending}
              onClick={() =>
                remove.mutate({ id: target.id, videoId: target.video.id }, { onSuccess: close })
              }
            >
              Delete
            </button>
          </div>
        </>
      )}
    </Dialog>
  )
}
