import { useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router'

import { ApiError } from '../../api/client'
import { useGoogleSignIn } from '../../auth/hooks'
import { takeReturnPath } from '../../auth/returnPath'
import Logo from '../../components/Logo'
import type { AuthState } from './AuthPage'
import styles from './AuthPage.module.css'

const FAILED = "Google couldn't sign you in. Try again."

function messageFor(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "Can't reach ViTube. Check your connection and try again."
  }
  switch (error.status) {
    case 400: // the sign-in expired, or Google's answer didn't check out
    case 403: // a banned account or a terminated channel
    case 409: // the email belongs to another account
    case 502: // Google didn't answer
      return error.message
    case 429:
      return 'Too many attempts. Wait a few minutes, then try again.'
    default:
      return FAILED
  }
}

/** Google sends the user back here: the page hands Google's answer to the API, then moves on. */
export default function GoogleCallbackPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const signIn = useGoogleSignIn()
  const sent = useRef(false)

  useEffect(() => {
    if (sent.current) return // StrictMode runs effects twice, and a code works only once
    sent.current = true
    const returnPath = takeReturnPath()
    const backToSignIn = (error?: string) => {
      const authState: AuthState = { from: returnPath, error }
      void navigate('/login', { replace: true, state: authState })
    }
    const code = params.get('code')
    const state = params.get('state')
    if (params.get('error') === 'access_denied') {
      backToSignIn() // the user chose not to: nothing went wrong
    } else if (!code || !state) {
      backToSignIn(FAILED)
    } else {
      signIn.mutateAsync({ code, state }).then(
        () => navigate(returnPath, { replace: true }),
        (error: unknown) => backToSignIn(messageFor(error)),
      )
    }
  }, [params, navigate, signIn])

  return (
    <div className={styles.page}>
      <title>Sign in - ViTube</title>
      <main className={styles.card} aria-busy="true">
        <div className={styles.progress} />
        <div className={styles.intro}>
          <span className={styles.logo}>
            <Logo size={40} wordmark={false} />
          </span>
          <h1 className={styles.title}>Signing in</h1>
          <p className={styles.subtitle}>with your Google account</p>
        </div>
      </main>
    </div>
  )
}
