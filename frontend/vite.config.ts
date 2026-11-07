import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import sirv from 'sirv'
import type { Plugin } from 'vite'
import { defineConfig } from 'vitest/config'

// Dev server proxies the API to the Docker stack (nginx on :80),
// or to a backend run from the IDE: API_PROXY=http://localhost:8000 npm run dev
// Keeps the browser's Host: the API refuses writes whose Origin doesn't match it (ADR 0005).
const api = { target: process.env.API_PROXY ?? 'http://localhost', changeOrigin: false }

// Dev only: serves the demo videos and thumbnails offline (demo-data/README.md). sirv handles Range for seeking.
function demoData(): Plugin {
  const root = fileURLToPath(new URL('../demo-data', import.meta.url))
  return {
    name: 'demo-data',
    apply: 'serve',
    configureServer(server) {
      for (const dir of ['videos', 'thumbnails']) {
        server.middlewares.use(`/demo-data/${dir}`, sirv(`${root}/${dir}`, { dev: true }))
      }
    },
  }
}

export default defineConfig({
  plugins: [react(), demoData()],
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
    unstubGlobals: true,
  },
})
