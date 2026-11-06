import { type InputHTMLAttributes, type Ref, useId } from 'react'

import Icon from './Icon'
import styles from './TextField.module.css'

interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'placeholder'> {
  label: string
  hint?: string
  error?: string
  ref?: Ref<HTMLInputElement>
}

/** An outlined field whose label moves up on focus or input (Material 3, as on Google's pages). */
export default function TextField({ label, hint, error, id, ref, ...input }: TextFieldProps) {
  const ownId = useId()
  const inputId = id ?? ownId
  const noteId = `${inputId}-note`
  const note = error ?? hint

  return (
    <div className={error ? `${styles.field} ${styles.invalid}` : styles.field}>
      <div className={styles.box}>
        {/* The blank placeholder lets CSS tell an empty field (:placeholder-shown). */}
        <input
          ref={ref}
          id={inputId}
          className={styles.input}
          placeholder=" "
          aria-invalid={error ? true : undefined}
          aria-describedby={note ? noteId : undefined}
          {...input}
        />
        <label htmlFor={inputId} className={styles.label}>
          {label}
        </label>
      </div>
      {note && (
        <p id={noteId} className={styles.note}>
          {error && <Icon name="error" size={16} />}
          {note}
        </p>
      )}
    </div>
  )
}
