import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { createMemoryRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'

import { createQueryClient } from '../api/queryClient'
import { routes } from '../app/routes'

/** The whole app at a path, as main.tsx renders it. Returns the router to check navigation. */
export function renderApp(path: string, state?: unknown) {
  const url = new URL(path, 'http://localhost')
  const router = createMemoryRouter(routes, {
    initialEntries: [{ pathname: url.pathname, search: url.search, state }],
  })
  render(
    <QueryClientProvider client={createQueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}
