import { type CSSProperties, useId } from 'react'

import Icon from '../components/Icon'
import { CATEGORIES, CATEGORY_LABELS } from '../videos/categories'
import type { Category, Visibility } from '../videos/types'
import { VISIBILITY_LABELS } from '../videos/visibility'
import type { VideoDetails } from './details'
import styles from './UploadDialog.module.css'

const TITLE_MAX = 100
const DESCRIPTION_MAX = 5000

const VISIBILITY: { value: Visibility; label: string; hint: string }[] = [
  {
    value: 'private',
    label: VISIBILITY_LABELS.private,
    hint: 'Only you and people you choose can watch your video',
  },
  {
    value: 'unlisted',
    label: VISIBILITY_LABELS.unlisted,
    hint: 'Anyone with the video link can watch your video',
  },
  { value: 'public', label: VISIBILITY_LABELS.public, hint: 'Everyone can watch your video' },
]

/** YouTube Studio's details form: title, description, category and visibility. */
export default function DetailsFields({
  details,
  onChange,
}: {
  details: VideoDetails
  onChange: (details: VideoDetails) => void
}) {
  const categoryId = useId()
  const visibilityName = useId()
  const set = (changes: Partial<VideoDetails>) => onChange({ ...details, ...changes })

  return (
    <>
      <h3 className={styles.section}>Details</h3>
      <TextArea
        label="Title (required)"
        value={details.title}
        maxLength={TITLE_MAX}
        rows={2}
        required
        onChange={(title) => set({ title })}
      />
      <TextArea
        label="Description"
        value={details.description}
        maxLength={DESCRIPTION_MAX}
        rows={6}
        placeholder="Tell viewers about your video"
        onChange={(description) => set({ description })}
      />
      <div>
        <h3 className={styles.section}>Category</h3>
        <p className={styles.sectionHint}>
          Add your video to a category so viewers can find it more easily
        </p>
        <div className={`${styles.box} ${styles.selectBox}`}>
          <label htmlFor={categoryId} className={styles.boxLabel}>
            Category
          </label>
          <select
            id={categoryId}
            className={styles.select}
            value={details.category}
            onChange={(event) => set({ category: event.target.value as Category })}
          >
            {CATEGORIES.map((id) => (
              <option key={id} value={id}>
                {CATEGORY_LABELS[id]}
              </option>
            ))}
          </select>
          <span className={styles.selectArrow}>
            <Icon name="chevronDown" />
          </span>
        </div>
      </div>
      <fieldset className={styles.visibility}>
        <legend className={styles.section}>Visibility</legend>
        <p className={styles.sectionHint}>Choose who can watch your video</p>
        {VISIBILITY.map((option) => (
          <label key={option.value} className={styles.option}>
            <input
              type="radio"
              name={visibilityName}
              value={option.value}
              checked={details.visibility === option.value}
              onChange={() => set({ visibility: option.value })}
            />
            <span>
              <span className={styles.optionLabel}>{option.label}</span>
              <span className={styles.optionHint}>{option.hint}</span>
            </span>
          </label>
        ))}
      </fieldset>
    </>
  )
}

function TextArea({
  label,
  value,
  maxLength,
  onChange,
  ...rest
}: {
  label: string
  value: string
  maxLength: number
  rows: number
  required?: boolean
  placeholder?: string
  onChange: (value: string) => void
}) {
  const id = useId()
  return (
    <div className={styles.box}>
      <label htmlFor={id} className={styles.boxLabel}>
        {label}
      </label>
      <textarea
        id={id}
        className={styles.textarea}
        value={value}
        maxLength={maxLength}
        onChange={(event) => onChange(event.target.value)}
        style={{ '--rows': rest.rows } as CSSProperties}
        {...rest}
      />
      <span className={styles.counter} aria-hidden="true">
        {value.length}/{maxLength}
      </span>
    </div>
  )
}
