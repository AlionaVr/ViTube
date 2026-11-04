import {Link} from 'react-router'

import EmptyState from '../components/EmptyState'

export default function NotFoundPage() {
    return (
        <EmptyState title="This page isn't available">
            <Link to="/">Go to the home page</Link>
        </EmptyState>
    )
}
