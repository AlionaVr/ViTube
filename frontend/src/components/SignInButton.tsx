import { Link } from 'react-router'

import Icon from './Icon'
import styles from './SignInButton.module.css'

export default function SignInButton() {
  return (
    <Link to="/login" className={styles.button}>
      <Icon name="account" />
      Sign in
    </Link>
  )
}
