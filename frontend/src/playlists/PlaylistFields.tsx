import { DESCRIPTION_MAX } from './limits'
import styles from './PlaylistFields.module.css'
import type { Visibility } from './types'
import { VISIBILITY } from './visibility'

const CHOICES = ['private', 'unlisted', 'public'] as const

export function PrivacySelect({
  value,
  onChange,
}: {
  value: Visibility
  onChange: (value: Visibility) => void
}) {
  return (
    <label className={styles.field}>
      <span>Privacy</span>
      <select
        className={styles.control}
        value={value}
        onChange={(event) => onChange(event.target.value as Visibility)}
      >
        {CHOICES.map((choice) => (
          <option key={choice} value={choice}>
            {VISIBILITY[choice].label}
          </option>
        ))}
      </select>
    </label>
  )
}

export function DescriptionField({
  value,
  onChange,
}: {
  value: string
  onChange: (value: string) => void
}) {
  return (
    <label className={styles.field}>
      <span>Description</span>
      <textarea
        className={`${styles.control} ${styles.text}`}
        value={value}
        maxLength={DESCRIPTION_MAX}
        rows={4}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}
