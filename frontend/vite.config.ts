import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Dev server proxies the API to the Docker stack (nginx on :80),
// or to a backend run from the IDE: API_PROXY=http://localhost:8000 npm run dev
const api = process.env.API_PROXY ?? 'http://localhost'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': api,
      '/docs': api,
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    restoreMocks: true,
  },
})
