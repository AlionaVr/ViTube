import { type FormEvent, useRef, useState } from 'react'
import { Link, Navigate, useLocation } from 'react-router'

import { ApiError } from '../../api/client'
import { useMe, useSignIn, useSignUp } from '../../auth/hooks'
import Icon from '../../components/Icon'
import Logo from '../../components/Logo'
import TextField from '../../components/TextField'
import styles from './AuthPage.module.css'

type Mode = 'signin' | 'signup'

const MIN_PASSWORD = 8 // the server's rule for new passwords
const MAX_PASSWORD = 128

const TEXT = {
  signin: {
    title: 'Sign in',
    subtitle: 'to continue to ViTube',
    submit: 'Sign in',
    other: { label: 'Create account', to: '/signup' },
    passwordAutoComplete: 'current-password',
    passwordHint: undefined,
  },
  signup: {
    title: 'Create a ViTube account',
    subtitle: 'Enter your email and a password',
    submit: 'Create account',
    other: { label: 'Sign in instead', to: '/login' },
    passwordAutoComplete: 'new-password',
    passwordHint: `Use ${MIN_PASSWORD} or more characters`,
  },
} as const

interface Errors {
  email?: string
  password?: string
  form?: string
}

function checkInput(mode: Mode, email: string, password: string): Errors {
  const errors: Errors = {}
  if (!email.trim()) errors.email = 'Enter an email'
  if (!password) errors.password = 'Enter a password'
  else if (mode === 'signup' && password.length < MIN_PASSWORD) {
    errors.password = `Use ${MIN_PASSWORD} characters or more for your password`
  }
  return errors
}

function errorsFrom(error: unknown): Errors {
  if (!(error instanceof ApiError)) {
    return { form: "Can't reach ViTube. Check your connection and try again." }
  }
  switch (error.status) {
    case 401:
      return { password: 'Wrong email or password. Try again.' }
    case 409:
      return { email: 'This email is already registered. Sign in instead.' }
    case 422: // passwords are checked here first, so only the email is left
      return { email: 'Enter a valid email address' }
    case 429:
      return { form: 'Too many attempts. Wait a few minutes, then try again.' }
    default:
      return { form: "ViTube can't do this right now. Try again in a moment." }
  }
}

export default function AuthPage({ mode }: { mode: Mode }) {
  const text = TEXT[mode]
  const location = useLocation()
  const me = useMe()
  const signIn = useSignIn()
  const signUp = useSignUp()
  const submit = mode === 'signin' ? signIn : signUp

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [errors, setErrors] = useState<Errors>({})
  const emailRef = useRef<HTMLInputElement>(null)
  const passwordRef = useRef<HTMLInputElement>(null)

  // Signed in (also right after this form succeeds): back to where the user came from.
  if (me.data) {
    const from = (location.state as { from?: string } | null)?.from ?? '/'
    return <Navigate to={from} replace />
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (submit.isPending) return // Enter in a field while a request runs
    let found = checkInput(mode, email, password)
    if (!found.email && !found.password) {
      try {
        await submit.mutateAsync({ email: email.trim(), password })
        return
      } catch (error) {
        found = errorsFrom(error)
      }
    }
    setErrors(found)
    if (found.email) emailRef.current?.focus()
    else if (found.password) passwordRef.current?.focus()
  }

  return (
    <div className={styles.page}>
      <title>{`${text.title} - ViTube`}</title>
      <main className={styles.card} aria-busy={submit.isPending}>
        {submit.isPending && <div className={styles.progress} />}
        <div className={styles.intro}>
          {/* Only the mark, like the logo on Google's sign-in card. */}
          <Link to="/" className={styles.logo} aria-label="ViTube home">
            <Logo size={40} wordmark={false} />
          </Link>
          <h1 className={styles.title}>{text.title}</h1>
          <p className={styles.subtitle}>{text.subtitle}</p>
        </div>

        <form className={styles.form} onSubmit={handleSubmit} noValidate>
          {/* Not disabled while a request runs: focus must reach a field that gets an error. */}
          <div className={styles.fields}>
            <TextField
              ref={emailRef}
              label="Email"
              type="email"
              autoComplete="email"
              value={email}
              error={errors.email}
              onChange={(event) => setEmail(event.target.value)}
            />
            <TextField
              ref={passwordRef}
              label="Password"
              type={showPassword ? 'text' : 'password'}
              autoComplete={text.passwordAutoComplete}
              maxLength={MAX_PASSWORD}
              value={password}
              hint={text.passwordHint}
              error={errors.password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <label className={styles.checkbox}>
              <span className={styles.box}>
                <input
                  type="checkbox"
                  checked={showPassword}
                  onChange={(event) => setShowPassword(event.target.checked)}
                />
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
                </svg>
              </span>
              Show password
            </label>
            {/* Below the fields, next to the button: the fields stay level with the title. */}
            {errors.form && (
              <p className={styles.alert} role="alert">
                <Icon name="errorFill" size={16} />
                {errors.form}
              </p>
            )}
          </div>

          <div className={styles.actions}>
            <Link to={text.other.to} state={location.state} className={styles.secondary}>
              {text.other.label}
            </Link>
            <button type="submit" className={styles.primary} disabled={submit.isPending}>
              {text.submit}
            </button>
          </div>
        </form>
      </main>
    </div>
  )
}
