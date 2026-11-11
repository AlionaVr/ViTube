import { SelectField, TextAreaField } from '../components/TextField'
import { DESCRIPTION_MAX } from './limits'
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
    <SelectField
      label="Privacy"
      value={value}
      onChange={(event) => onChange(event.target.value as Visibility)}
    >
      {CHOICES.map((choice) => (
        <option key={choice} value={choice}>
          {VISIBILITY[choice].label}
        </option>
      ))}
    </SelectField>
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
    <TextAreaField
      label="Description"
      value={value}
      maxLength={DESCRIPTION_MAX}
      hint={`${value.length}/${DESCRIPTION_MAX}`}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}
