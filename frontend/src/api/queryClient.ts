import { QueryClient } from '@tanstack/react-query'

import { ApiError } from './client'

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // A 4xx answer won't change on a retry. Network and 5xx errors get two more tries.
        retry: (failures, error) =>
          !(error instanceof ApiError && error.status < 500) && failures < 2,
      },
    },
  })
}
