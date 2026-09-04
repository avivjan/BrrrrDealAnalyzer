import type { Page } from '@playwright/test';

/**
 * A frozen clock, installed before the first navigation of every test.
 *
 * Three of this app's behaviours are pure timing — the 250 ms modal settle
 * window, the 500 ms re-analyze debounce and the 2 s autosave debounce — and
 * the only honest way to characterize them is to own the clock rather than
 * sleep and hope.
 *
 * `install()` alone is not enough: it fakes the time source but leaves it
 * *ticking*, so a debounce still fires on its own while Playwright is busy
 * doing something else and "no request was sent" degrades into "no request was
 * sent yet". `pauseAt()` is what actually stops the clock, so it is paired
 * with `install()` here and the page never sees a moment pass that a spec did
 * not ask for by name.
 */
const START_TIME = new Date('2026-09-04T09:59:00');

/** What every test's `Date.now()` reads until it calls `settle`. */
export const FIXED_TIME = new Date('2026-09-04T10:00:00');

export async function installClock(page: Page): Promise<void> {
  await page.clock.install({ time: START_TIME });
  // `pauseAt` only ever jumps forward, hence the one-minute run-up.
  await page.clock.pauseAt(FIXED_TIME);
}

/**
 * Advance page time by `ms`, then give the network a real moment to carry
 * whatever those timers fired. Timers are faked; sockets are not.
 */
export async function settle(page: Page, ms: number): Promise<void> {
  await page.clock.runFor(ms);
  await page.waitForTimeout(150);
}
