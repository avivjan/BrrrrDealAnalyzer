/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { configDefaults } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  build: {
    target: ['es2020', 'safari15', 'ios15', 'chrome100', 'firefox100'],
  },
  // Same-origin API in development (`VITE_API_URL=/api`), mirroring the
  // Netlify `/api/*` rewrite in public/_redirects. The default VITE_API_URL
  // (http://localhost:8000) keeps working too.
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false, rewrite: (path: string) => path.replace(/^\/api/, '') },
    },
  },
  test: {
    environment: 'node',
    setupFiles: ['src/test/setup.ts'],
    // `e2e/` is Playwright's, and its specs cannot run under Vitest at all;
    // without this they are swallowed by Vitest's default glob.
    exclude: [...configDefaults.exclude, 'e2e/**'],
  },
})
