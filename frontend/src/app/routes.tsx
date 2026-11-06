import type { RouteObject } from 'react-router'

import HomePage from '../pages/HomePage'
import NotFoundPage from '../pages/NotFoundPage'
import WatchPage from '../pages/watch/WatchPage'
import Layout from './Layout'

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'watch', element: <WatchPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
