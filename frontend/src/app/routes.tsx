import type { RouteObject } from 'react-router'

import AuthPage from '../pages/auth/AuthPage'
import HomePage from '../pages/HomePage'
import NotFoundPage from '../pages/NotFoundPage'
import Layout from './Layout'

export const routes: RouteObject[] = [
  // Outside Layout: full-page forms with no header or sidebar, like Google's sign-in.
  { path: '/login', element: <AuthPage mode="signin" /> },
  { path: '/signup', element: <AuthPage mode="signup" /> },
  {
    element: <Layout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
