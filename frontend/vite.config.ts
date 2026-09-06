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
  test: {
    environment: 'node',
    setupFiles: ['src/test/setup.ts'],
    // `e2e/` is Playwright's, and its specs cannot run under Vitest at all;
    // without this they are swallowed by Vitest's default glob.
    exclude: [...configDefaults.exclude, 'e2e/**'],
  },
})
