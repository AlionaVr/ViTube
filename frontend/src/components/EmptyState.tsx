import type {ReactNode} from 'react'

import styles from './EmptyState.module.css'

export default function EmptyState({title, children}: { title: string; children: ReactNode }) {
    return (
        <div className={styles.root}>
            <h1>{title}</h1>
            <p>{children}</p>
        </div>
    )
}
