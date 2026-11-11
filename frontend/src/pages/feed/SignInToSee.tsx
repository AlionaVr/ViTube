import Icon from '../../components/Icon'
import SignInButton from '../../components/SignInButton'
import styles from './SignInToSee.module.css'

/** What a guest sees on the subscription pages, as on YouTube. */
export default function SignInToSee() {
  return (
    <div className={styles.prompt}>
      <Icon name="subscriptions" size={120} />
      <h1 className={styles.title}>Don’t miss new videos</h1>
      <p className={styles.text}>Sign in to see updates from your favorite ViTube channels</p>
      <SignInButton />
    </div>
  )
}
