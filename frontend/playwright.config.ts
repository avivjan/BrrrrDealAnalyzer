import { defineConfig, devices } from '@playwright/test';
import { API_ORIGIN, APP_ORIGIN, APP_PORT } from './e2e/fixtures/env';

/**
 * Phase 0 Functional Characterization Suite (FCS layer L3).
 *
 * This suite freezes today's user-visible behaviour and the exact HTTP
 * contract *before* any visual change, and is re-run unchanged at every later
 * phase of the UI overhaul. It runs against the real FastAPI backend on a
 * throwaway SQLite database (see `e2e/backend/serve_throwaway.py`).
 *
 * Motion is reduced on the four functional projects on purpose: a
 * characterization suite must assert what the app *does*, not race what it
 * animates. The one motion-sensitive concern (an overlay that must cover the
 * viewport the instant it appears) is covered by the extra `chromium-motion`
 * project, which runs only the `@motion`-tagged specs with animations on.
 */

/** Animations off — the default for every functional project. */
const REDUCED = { reducedMotion: 'reduce' } as const;

export default defineConfig({
  testDir: './e2e/flows',
  outputDir: './test-results',

  // One shared backend database, so tests must not overlap.
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: !!process.env.CI,

  timeout: 90_000,
  expect: { timeout: 15_000 },

  reporter: [
    ['list'],
    ['json', { outputFile: 'e2e/reports/last-run.json' }],
  ],

  use: {
    baseURL: APP_ORIGIN,
    trace: 'retain-on-failure',
    // Real geolocation is never queried (REPS is unconfigured here), but the
    // permission has to be grantable for the timer flow not to prompt.
    permissions: ['geolocation'],
    geolocation: { latitude: 40.7128, longitude: -74.006 },
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], contextOptions: { ...REDUCED } },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'], contextOptions: { ...REDUCED } },
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 14'], contextOptions: { ...REDUCED } },
    },
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 7'], contextOptions: { ...REDUCED } },
    },
    {
      // Same browser, animations ON. Only the @motion specs run here.
      name: 'chromium-motion',
      grep: /@motion/,
      use: {
        ...devices['Desktop Chrome'],
        contextOptions: { reducedMotion: 'no-preference' },
      },
    },
  ],

  webServer: [
    {
      command: 'python3 e2e/backend/serve_throwaway.py',
      url: `${API_ORIGIN}/helloworld`,
      reuseExistingServer: !process.env.CI,
      stdout: 'pipe',
      stderr: 'pipe',
      timeout: 120_000,
    },
    {
      // `BackEnd/main.py` only allows localhost:5173 / :3000 through CORS, so
      // the suite runs the production bundle behind `vite preview` on 5173
      // rather than the dev server on a random port.
      command: `VITE_API_URL=${API_ORIGIN} npm run build && npx vite preview --port ${APP_PORT} --strictPort`,
      url: APP_ORIGIN,
      reuseExistingServer: !process.env.CI,
      stdout: 'pipe',
      stderr: 'pipe',
      timeout: 180_000,
    },
  ],
});
