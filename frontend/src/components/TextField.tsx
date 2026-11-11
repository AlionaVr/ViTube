import {
  type InputHTMLAttributes,
  type ReactNode,
  type Ref,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
  useId,
} from 'react'

import Icon from './Icon'
import styles from './TextField.module.css'

interface FieldProps {
  label: string
  hint?: string
  error?: string
}

/** The outlined frame (Material 3, as on Google's pages): the control, its label, a note below. */
function Frame({
  id,
  label,
  hint,
  error,
  children,
  after,
}: FieldProps & { id: string; children: ReactNode; after?: ReactNode }) {
  const note = error ?? hint
  return (
    <div className={error ? `${styles.field} ${styles.invalid}` : styles.field}>
      <div className={styles.box}>
        {children}
        {/* Right after the control: CSS moves it up from the control's state (`+ .label`). */}
        <label htmlFor={id} className={styles.label}>
          {label}
        </label>
        {after}
      </div>
      {note && (
        <p id={`${id}-note`} className={styles.note}>
          {error && <Icon name="errorFill" size={16} />}
          {note}
        </p>
      )}
    </div>
  )
}

function described(id: string, { hint, error }: Pick<FieldProps, 'hint' | 'error'>) {
  return {
    id,
    'aria-invalid': error ? true : undefined,
    'aria-describedby': (error ?? hint) ? `${id}-note` : undefined,
  }
}

interface TextFieldProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, 'placeholder'>, FieldProps {
  ref?: Ref<HTMLInputElement>
}

/** One line; the label moves up on focus or input. */
export default function TextField({ label, hint, error, id, ref, ...input }: TextFieldProps) {
  const inputId = useId()
  const fieldId = id ?? inputId
  return (
    <Frame id={fieldId} label={label} hint={hint} error={error}>
      {/* The blank placeholder lets CSS tell an empty field (:placeholder-shown). */}
      <input
        ref={ref}
        className={styles.input}
        placeholder=" "
        {...described(fieldId, { hint, error })}
        {...input}
      />
    </Frame>
  )
}

type TextAreaFieldProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'placeholder'> &
  FieldProps

/** Several lines in the same frame; grows with the text. */
export function TextAreaField({ label, hint, error, id, ...area }: TextAreaFieldProps) {
  const areaId = useId()
  const fieldId = id ?? areaId
  return (
    <Frame id={fieldId} label={label} hint={hint} error={error}>
      <textarea
        className={`${styles.input} ${styles.multiline}`}
        placeholder=" "
        {...described(fieldId, { hint, error })}
        {...area}
      />
    </Frame>
  )
}

type SelectFieldProps = SelectHTMLAttributes<HTMLSelectElement> & FieldProps

/** A native select (keyboard and screen readers as usual) in the same frame. */
export function SelectField({ label, hint, error, id, children, ...select }: SelectFieldProps) {
  const selectId = useId()
  const fieldId = id ?? selectId
  return (
    <Frame
      id={fieldId}
      label={label}
      hint={hint}
      error={error}
      after={
        <span className={styles.chevron}>
          <Icon name="arrowDropDown" />
        </span>
      }
    >
      <select
        className={`${styles.input} ${styles.select}`}
        {...described(fieldId, { hint, error })}
        {...select}
      >
        {children}
      </select>
    </Frame>
  )
}
