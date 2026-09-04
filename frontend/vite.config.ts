/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  build: {
    target: ['es2020', 'safari15', 'ios15', 'chrome100', 'firefox100'],
  },
  test: {
    environment: 'node',
  },
})
