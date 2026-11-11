import Icon, { type IconName } from '../../components/Icon'
import SignInButton from '../../components/SignInButton'
import styles from './SignInToSee.module.css'

interface SignInToSeeProps {
  icon: IconName
  title: string
  text: string
}

/** What a guest sees on a page of their own things (subscriptions, Watch later), as on YouTube. */
export default function SignInToSee({ icon, title, text }: SignInToSeeProps) {
  return (
    <div className={styles.prompt}>
      <Icon name={icon} size={120} />
      <h1 className={styles.title}>{title}</h1>
      <p className={styles.text}>{text}</p>
      <SignInButton />
    </div>
  )
}
