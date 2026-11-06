import { useState } from 'react'
import { Link } from 'react-router'

import { useRateComment, useReplies } from '../../../comments/hooks'
import type { Comment } from '../../../comments/types'
import Avatar from '../../../components/Avatar'
import ClampedText from '../../../components/ClampedText'
import Icon from '../../../components/Icon'
import SignInGate from '../../../components/SignInGate'
import Spinner from '../../../components/Spinner'
import { formatCompact, formatTimeAgo } from '../../../lib/format'
import buttons from '../../../styles/buttons.module.css'
import { channelUrl } from '../../../videos/paths'
import CommentComposer from './CommentComposer'
import styles from './Comments.module.css'

interface CommentItemProps {
  comment: Comment
  videoId: string
  /** The top-level comment a reply belongs to; replies to replies go there too. */
  threadId?: string
}

function Replies({ videoId, commentId }: { videoId: string; commentId: string }) {
  const replies = useReplies(videoId, commentId, true)
  if (replies.isPending) return <Spinner label="Loading replies" size={24} />
  return (
    <div className={styles.replies}>
      {replies.data?.pages
        .flatMap((page) => page.items)
        .map((reply) => (
          <CommentItem key={reply.id} comment={reply} videoId={videoId} threadId={commentId} />
        ))}
      {replies.hasNextPage && (
        <button
          type="button"
          className={`${buttons.pill} ${buttons.link} ${buttons.small}`}
          onClick={() => void replies.fetchNextPage()}
        >
          Show more replies
        </button>
      )}
    </div>
  )
}

export default function CommentItem({ comment, videoId, threadId }: CommentItemProps) {
  const rate = useRateComment(videoId)
  const [replying, setReplying] = useState(false)
  const [showReplies, setShowReplies] = useState(false)
  const isReply = threadId !== undefined
  const liked = comment.my_rating === 'like'
  const disliked = comment.my_rating === 'dislike'
  const { author } = comment

  return (
    <article className={isReply ? `${styles.comment} ${styles.reply}` : styles.comment}>
      <Link to={channelUrl(author.handle)} tabIndex={-1} aria-hidden="true">
        <Avatar name={author.name} src={author.avatar_url} size={isReply ? 24 : 40} />
      </Link>
      <div className={styles.body}>
        <div className={styles.meta}>
          <Link
            to={channelUrl(author.handle)}
            className={comment.by_owner ? `${styles.author} ${styles.owner}` : styles.author}
          >
            @{author.handle}
          </Link>
          <span className={styles.time}>{formatTimeAgo(comment.published_at)}</span>
        </div>
        <div className={styles.text}>
          <ClampedText text={comment.text} lines={4} />
        </div>

        <div className={styles.toolbar}>
          <SignInGate
            title="Like this comment?"
            text="Sign in to make your opinion count."
            onAction={() => rate.mutate({ id: comment.id, rating: liked ? 'none' : 'like' })}
          >
            {(props) => (
              <button
                type="button"
                className={styles.tool}
                aria-label="Like this comment"
                aria-pressed={liked}
                {...props}
              >
                <Icon name={liked ? 'likeFill' : 'like'} size={20} />
              </button>
            )}
          </SignInGate>
          <span className={styles.likes}>
            {comment.like_count > 0 && formatCompact(comment.like_count)}
          </span>
          <SignInGate
            title="Don’t like this comment?"
            text="Sign in to make your opinion count."
            onAction={() => rate.mutate({ id: comment.id, rating: disliked ? 'none' : 'dislike' })}
          >
            {(props) => (
              <button
                type="button"
                className={styles.tool}
                aria-label="Dislike this comment"
                aria-pressed={disliked}
                {...props}
              >
                <Icon name={disliked ? 'dislikeFill' : 'dislike'} size={20} />
              </button>
            )}
          </SignInGate>
          <SignInGate
            title="Want to join the conversation?"
            text="Sign in to continue."
            onAction={() => setReplying(true)}
          >
            {(props) => (
              <button
                type="button"
                className={`${buttons.pill} ${buttons.text} ${buttons.small}`}
                {...props}
              >
                Reply
              </button>
            )}
          </SignInGate>
        </div>

        {replying && (
          <CommentComposer
            videoId={videoId}
            parentId={threadId ?? comment.id}
            autoFocus
            onDone={() => {
              setReplying(false)
              if (!isReply) setShowReplies(true)
            }}
          />
        )}

        {!isReply && comment.reply_count > 0 && (
          <button
            type="button"
            className={`${buttons.pill} ${buttons.link} ${styles.repliesToggle}`}
            aria-expanded={showReplies}
            onClick={() => setShowReplies((value) => !value)}
          >
            <Icon name={showReplies ? 'chevronUp' : 'chevronDown'} />
            {comment.reply_count} {comment.reply_count === 1 ? 'reply' : 'replies'}
          </button>
        )}
        {showReplies && <Replies videoId={videoId} commentId={comment.id} />}
      </div>
    </article>
  )
}
