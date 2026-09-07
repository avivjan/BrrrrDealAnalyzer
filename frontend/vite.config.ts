/// <reference types="vitest/config" />
import { readFileSync } from 'node:fs'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { configDefaults } from 'vitest/config'

/**
 * The production Content-Security-Policy from public/_headers (what Netlify
 * serves), so `vite preview` -- and therefore every Playwright run -- executes
 * the built app under the exact policy. The policy names the production API
 * host and localhost:8000; when the bundle is built for another absolute API
 * origin (the e2e backend), that origin takes localhost:8000's place.
 */
export function productionCsp(apiUrl = process.env.VITE_API_URL): string | undefined {
  const line = readFileSync(new URL('./public/_headers', import.meta.url), 'utf8')
    .split('\n')
    .find((l) => l.trim().startsWith('Content-Security-Policy:'))
  if (!line) return undefined
  const value = line.trim().slice('Content-Security-Policy:'.length).trim()
  return apiUrl && /^https?:\/\//.test(apiUrl) ? value.replace('http://localhost:8000', new URL(apiUrl).origin) : value
}

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
  preview: {
    headers: productionCsp() ? { 'Content-Security-Policy': productionCsp()! } : {},
  },
  test: {
    environment: 'node',
    setupFiles: ['src/test/setup.ts'],
    // `e2e/` is Playwright's, and its specs cannot run under Vitest at all;
    // without this they are swallowed by Vitest's default glob.
    exclude: [...configDefaults.exclude, 'e2e/**'],
  },
})
