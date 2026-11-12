import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Dev server proxies the API to the Docker stack (nginx on :80),
// or to a backend run from the IDE: API_PROXY=http://localhost:8000 npm run dev
// Keeps the browser's Host: the API refuses writes whose Origin doesn't match it (ADR 0005).
const api = { target: process.env.API_PROXY ?? 'http://localhost', changeOrigin: false }

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': api,
      // Videos and thumbnails: nginx checks access, MinIO answers Range requests.
      '/media': api,
      // API docs: a page and Swagger UI files in the nginx image.
      '/docs': api,
      '/swagger': api,
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    restoreMocks: true,
    unstubGlobals: true,
  },
})
