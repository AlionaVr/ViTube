import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { createMemoryRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'

import { createQueryClient } from '../api/queryClient'
import { routes } from '../app/routes'

/** The whole app at a path, with a fresh query cache. Returns the router to check navigation. */
export function renderApp(path: string, state?: unknown) {
  const queryClient = createQueryClient()
  // Errors show at once; the retry policy has its own tests.
  const defaults = queryClient.getDefaultOptions()
  queryClient.setDefaultOptions({ ...defaults, queries: { ...defaults.queries, retry: false } })

  const url = new URL(path, 'http://localhost')
  const router = createMemoryRouter(routes, {
    initialEntries: [{ pathname: url.pathname, search: url.search, state }],
  })
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}
