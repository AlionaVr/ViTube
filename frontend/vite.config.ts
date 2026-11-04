import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Dev server proxies the API to the running Docker stack (nginx on :80).
const stack = 'http://localhost'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': stack,
      '/docs': stack,
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    restoreMocks: true,
  },
})
