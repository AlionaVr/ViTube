import { Link, useLocation } from 'react-router'

import Icon from './Icon'
import styles from './SignInButton.module.css'

export default function SignInButton() {
  const location = useLocation()
  // After signing in, the user comes back to this page.
  return (
    <Link
      to="/login"
      state={{ from: location.pathname + location.search }}
      className={styles.button}
    >
      <Icon name="account" />
      Sign in
    </Link>
  )
}
