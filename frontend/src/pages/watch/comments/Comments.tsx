import { useState } from 'react'

import { useComments } from '../../../comments/hooks'
import type { CommentSort } from '../../../comments/types'
import ErrorState from '../../../components/ErrorState'
import Icon from '../../../components/Icon'
import Popover from '../../../components/Popover'
import Spinner from '../../../components/Spinner'
import { useInfiniteScroll } from '../../../hooks/useInfiniteScroll'
import { formatExact } from '../../../lib/format'
import buttons from '../../../styles/buttons.module.css'
import type { Video } from '../../../videos/types'
import CommentComposer from './CommentComposer'
import CommentItem from './CommentItem'
import styles from './Comments.module.css'

const SORTS: { id: CommentSort; label: string }[] = [
  { id: 'top', label: 'Top comments' },
  { id: 'new', label: 'Newest first' },
]

function SortMenu({
  sort,
  onChange,
}: {
  sort: CommentSort
  onChange: (sort: CommentSort) => void
}) {
  return (
    <Popover
      label="Sort comments"
      role="menu"
      trigger={(props) => (
        <button
          type="button"
          className={`${buttons.pill} ${buttons.text} ${buttons.iconLeading}`}
          {...props}
        >
          <Icon name="sort" />
          Sort by
        </button>
      )}
    >
      {(close) => (
        <div className={styles.sortMenu}>
          {SORTS.map((option) => (
            <button
              key={option.id}
              type="button"
              role="menuitemradio"
              aria-checked={option.id === sort}
              className={styles.sortItem}
              onClick={() => {
                onChange(option.id)
                close()
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
      )}
    </Popover>
  )
}

export default function Comments({ video }: { video: Video }) {
  const [sort, setSort] = useState<CommentSort>('top')
  const comments = useComments(video.id, sort)
  const sentinel = useInfiniteScroll<HTMLDivElement>(
    () => void comments.fetchNextPage(),
    comments.hasNextPage && !comments.isFetchingNextPage && !comments.isFetchNextPageError,
  )
  const count = video.comment_count

  return (
    <section className={styles.section} aria-labelledby="comments-title">
      <div className={styles.header}>
        <h2 id="comments-title" className={styles.count}>
          {formatExact(count)} {count === 1 ? 'Comment' : 'Comments'}
        </h2>
        <SortMenu sort={sort} onChange={setSort} />
      </div>
      <CommentComposer videoId={video.id} />

      {comments.isPending ? (
        <div className={styles.loading}>
          <Spinner label="Loading comments" />
        </div>
      ) : !comments.data ? (
        <ErrorState title="Can’t load comments" onRetry={() => void comments.refetch()} />
      ) : (
        <>
          {comments.data.pages
            .flatMap((page) => page.items)
            .map((comment) => (
              <CommentItem key={comment.id} comment={comment} videoId={video.id} />
            ))}
          <div ref={sentinel} />
          {comments.isFetchingNextPage && (
            <div className={styles.loading}>
              <Spinner label="Loading more comments" />
            </div>
          )}
        </>
      )}
    </section>
  )
}
