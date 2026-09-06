import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { gzipSync } from 'node:zlib';

import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

import { API_ORIGIN } from '../fixtures/env';
import { Seeder } from '../fixtures/seed';

/**
 * The UI v3 performance budget, measured in a real browser.
 *
 * The plan's guardrail reads: "main chunk ≤ +12 kB gz vs baseline, CLS ≤ 0.05
 * per route, zero > 50 ms long tasks idle on boards with 20 cards". Three
 * numbers, three kinds of check:
 *
 *  - **CLS per route** is asserted. A `layout-shift` observer is installed
 *    before the page's first script runs, every shift without recent input is
 *    summed, and the route gets one real second after its ready hook to do
 *    whatever it does late (a fetch resolving, a font swapping in).
 *  - **Long tasks** are asserted, on the two boards with 20 and 8 cards
 *    seeded, three real seconds of idle each, and again on the liquidity chart
 *    during a 400 px pan. The observer is armed only once the surface is on
 *    screen, so the bundle's own parse-and-execute — a long task on any
 *    machine, and not what the budget is about — is reported but not counted.
 *  - **Bundle size** is *annotated*, never asserted: the budget is a delta
 *    against a baseline this spec cannot know, so it puts the number in the
 *    run report and the progress file compares by hand.
 *
 * ## Why this spec does not use the shared `test`
 *
 * `e2e/fixtures/index.ts` installs a paused clock before the first
 * navigation of every test — exactly right for the characterization suite,
 * exactly wrong here. Layout shifts and long tasks are wall-clock phenomena:
 * a `PerformanceObserver` that only delivers on a frame nobody advances would
 * make every assertion pass for nothing. So this file imports `test` from
 * `@playwright/test`, lets time run, and does its own seeding through the
 * same `Seeder` the fixtures use — once per file, on a request context of its
 * own, swept in `afterAll` the way the fixture sweeps after each test.
 *
 * ## Projects
 *
 * Long-task and layout-shift entries are Chromium's; the plain tests run on
 * the functional `chromium` project (motion reduced), and the two board
 * tests have an `@motion` twin that runs on `chromium-motion` with every
 * v3 entrance and hover animation live — the budget has to hold there too.
 */

const CLS_BUDGET = 0.05;
const LONG_TASK_MS = 50;
const ACTIVE_DEALS = 20;
const BOUGHT_DEALS = 8;

/** The same route → ready-hook table as `flows/a11y.spec.ts`. */
const ROUTES: [name: string, path: string, ready: string][] = [
  ['landing', '/', 'landing.offer'],
  ['analyze', '/analyze', 'form.root'],
  ['my-deals', '/my-deals', 'mydeals.add-deal'],
  ['bought-deals', '/bought-deals', 'boughtdeals.edit-pipeline'],
  ['liquidity', '/liquidity', 'liquidity.add-flow'],
  ['reps', '/reps', 'reps.manual-entry'],
];

/** The two boards: route, card-hook prefix, and how many cards are seeded. */
const BOARDS: [name: string, path: string, cardPrefix: string, cards: number][] = [
  ['my-deals', '/my-deals', 'mydeals.card.', ACTIVE_DEALS],
  ['bought-deals', '/bought-deals', 'boughtdeals.card.', BOUGHT_DEALS],
];

/** Mirrors `SEED_HEADERS` in `fixtures/seed.ts`, which is not exported. */
const SEED_HEADERS = { 'x-e2e-seed': '1' };

interface LongTask {
  start: number;
  duration: number;
}

declare global {
  interface Window {
    __cls?: number;
    __longTasks?: LongTask[];
    __longTaskObserver?: PerformanceObserver;
    __longTasksArmedAt?: number;
  }
}

// --- project gating ---------------------------------------------------------

const isMotion = (title: string): boolean => title.includes('@motion');

test.beforeEach(({}, testInfo) => {
  const wanted = isMotion(testInfo.title) ? 'chromium-motion' : 'chromium';
  test.skip(
    testInfo.project.name !== wanted,
    `performance entries are Chromium's; this test runs on ${wanted} only`,
  );
});

// --- seeding, once per file -------------------------------------------------

let api: APIRequestContext | undefined;
let seeder: Seeder | undefined;

test.beforeAll(async ({ playwright }, testInfo) => {
  // The gate above skips every test on the other projects, but `beforeAll`
  // runs first; seeding 28 deals for a file that then does nothing is waste.
  if (!['chromium', 'chromium-motion'].includes(testInfo.project.name)) return;

  api = await playwright.request.newContext();
  seeder = new Seeder(api, API_ORIGIN);
  await seeder.snapshot();
  await seeder.resetDb();

  // 20 active deals across the five stages, all on section 1 — the tab
  // `MyDeals` opens on. The payload's own section is 2, so the 8 sources the
  // bought deals are promoted from stay off that tab and the board shows
  // exactly 20 cards.
  for (let i = 0; i < ACTIVE_DEALS; i += 1) {
    await seeder.seedActiveDeal('BRRRR', {
      section: 1,
      stage: 1 + (i % 5),
      address: `${100 + i} Perf St`,
    });
  }
  for (let i = 0; i < BOUGHT_DEALS; i += 1) {
    await seeder.seedBoughtDeal('BRRRR', { address: `${200 + i} Bought Ave` });
  }

  // An opening balance is what makes `/liquidity` render the chart rather
  // than its empty state (`hasData` in `LiquidityTimeline.vue`). The same
  // three fields `flows/liquidity.spec.ts` saves through the settings modal;
  // `resetDb` restores the snapshot afterwards.
  const settings = await api.put(`${API_ORIGIN}/liquidity/settings`, {
    headers: SEED_HEADERS,
    data: { opening_balance_k: 50, opening_balance_date: '2026-09-04', reserve_k: 5 },
  });
  if (!settings.ok()) {
    throw new Error(`PUT /liquidity/settings failed: ${settings.status()} ${await settings.text()}`);
  }
});

test.afterAll(async () => {
  await seeder?.resetDb();
  await api?.dispose();
});

// --- helpers ----------------------------------------------------------------

/**
 * Arm a `longtask` observer *now*, remembering when. Entries are buffered, so
 * the ones from before this moment (the bundle evaluating, the app mounting)
 * arrive too; `longTasksSince` keeps them apart from the ones that count.
 */
async function armLongTasks(page: Page): Promise<void> {
  await page.evaluate(() => {
    window.__longTasks = [];
    window.__longTasksArmedAt = performance.now();
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        window.__longTasks!.push({ start: entry.startTime, duration: entry.duration });
      }
    });
    observer.observe({ type: 'longtask', buffered: true });
    window.__longTaskObserver = observer;
  });
}

/** Long tasks split into the ones before arming (reported) and after (counted). */
async function longTasksSince(page: Page): Promise<{ before: LongTask[]; after: LongTask[] }> {
  return page.evaluate((threshold) => {
    const pending = window.__longTaskObserver?.takeRecords() ?? [];
    for (const entry of pending) {
      window.__longTasks!.push({ start: entry.startTime, duration: entry.duration });
    }
    const armedAt = window.__longTasksArmedAt ?? 0;
    const all = (window.__longTasks ?? []).filter((task) => task.duration > threshold);
    return {
      before: all.filter((task) => task.start < armedAt),
      after: all.filter((task) => task.start >= armedAt),
    };
  }, LONG_TASK_MS);
}

const describeTasks = (tasks: LongTask[]): string =>
  tasks.map((task) => `${Math.round(task.duration)} ms @ ${Math.round(task.start)} ms`).join(', ');

/** Put the load-phase long tasks in the report, so a regression there is visible too. */
function annotateLoadTasks(name: string, before: LongTask[]): void {
  test.info().annotations.push({
    type: 'long-tasks-during-load',
    description: `${name}: ${before.length}${before.length ? ` (${describeTasks(before)})` : ''}`,
  });
}

// --- CLS per route ----------------------------------------------------------

for (const [name, path, ready] of ROUTES) {
  test(`${name}: cumulative layout shift stays within budget`, async ({ page }) => {
    // Before any of the page's own scripts, on every navigation. The observer
    // is buffered so a shift that happens before this callback is registered
    // — there should be none, but `addInitScript` makes no promise about the
    // very first paint — is still counted.
    await page.addInitScript(() => {
      window.__cls = 0;
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries() as (PerformanceEntry & {
          value: number;
          hadRecentInput: boolean;
        })[]) {
          if (!entry.hadRecentInput) window.__cls = (window.__cls ?? 0) + entry.value;
        }
      }).observe({ type: 'layout-shift', buffered: true });
    });

    await page.goto(path);
    await expect(page.getByTestId(ready)).toBeVisible();
    // One real second after the ready hook: the store's fetch resolving, the
    // board filling in, a variable font arriving — whatever shifts late.
    await page.waitForTimeout(1000);

    const cls = await page.evaluate(() => window.__cls ?? 0);
    test.info().annotations.push({ type: 'cls', description: `${name}: ${cls.toFixed(4)}` });
    expect(cls, `${path}: cumulative layout shift`).toBeLessThanOrEqual(CLS_BUDGET);
  });
}

// --- long tasks on the boards, idle -----------------------------------------

for (const motion of [false, true]) {
  const tag = motion ? ' @motion' : '';
  for (const [name, path, cardPrefix, cards] of BOARDS) {
    test(`${name}: no long task while the board sits idle with ${cards} cards${tag}`, async ({
      page,
    }) => {
      await page.goto(path);
      const cardsOnBoard = page.locator(`[data-testid^="${cardPrefix}"]`);
      await expect(cardsOnBoard.first()).toBeVisible();
      await expect(cardsOnBoard).toHaveCount(cards);

      // Armed once the cards are there — the render is what the seed exists
      // to provoke, the parse-and-mount before it is not what "idle" means.
      await armLongTasks(page);
      await page.waitForTimeout(3000);

      const { before, after } = await longTasksSince(page);
      annotateLoadTasks(name, before);
      expect(
        after,
        `${path}: long tasks (> ${LONG_TASK_MS} ms) during 3 s idle: ${describeTasks(after)}`,
      ).toEqual([]);
    });
  }
}

// --- long tasks on the chart, panning ---------------------------------------

test('liquidity: panning the chart 400 px causes no long task', async ({ page }) => {
  await page.goto('/liquidity');
  const chart = page.getByTestId('chart.container');
  await expect(chart).toBeVisible();
  await expect(page.getByTestId('liquidity.loading')).toBeHidden();

  const box = await chart.boundingBox();
  expect(box, 'the chart has a box to drag').not.toBeNull();
  // Right edge to 400 px left of it. The chart takes pointer capture on
  // `pointerdown`, so the pan holds even where the chart is narrower than the
  // drag; 40 steps is roughly the pointermove cadence of a real 60 Hz drag.
  const y = box!.y + box!.height / 2;
  const from = box!.x + box!.width - 16;

  await armLongTasks(page);
  await page.mouse.move(from, y);
  await page.mouse.down();
  await page.mouse.move(from - 400, y, { steps: 40 });
  await page.mouse.up();
  // A beat for the observer to deliver what the drag queued.
  await page.waitForTimeout(250);

  const { before, after } = await longTasksSince(page);
  annotateLoadTasks('liquidity', before);
  expect(
    after,
    `/liquidity: long tasks (> ${LONG_TASK_MS} ms) during a 400 px pan: ${describeTasks(after)}`,
  ).toEqual([]);
});

// --- bundle line ------------------------------------------------------------

test('bundle: gzip size of dist/assets/*.js, for the progress file', async () => {
  // Resolved against this file, not the working directory (gate G8). The
  // config builds before `vite preview`, so `dist/` exists on a normal run;
  // a run against a dev server has nothing to weigh and says so.
  const assets = new URL('../../dist/assets/', import.meta.url);
  test.skip(!existsSync(assets), 'no dist/ build to measure');

  const rows = readdirSync(assets)
    .filter((file) => file.endsWith('.js'))
    .map((file) => {
      const url = new URL(file, assets);
      return { file, raw: statSync(url).size, gzip: gzipSync(readFileSync(url)).length };
    })
    .sort((a, b) => b.gzip - a.gzip);
  const total = rows.reduce((sum, row) => sum + row.gzip, 0);

  // Annotation only: the budget is "≤ +12 kB gz vs baseline" and the baseline
  // lives in the progress file, not here.
  test.info().annotations.push({ type: 'bundle-gzip-bytes', description: String(total) });
  test.info().annotations.push({
    type: 'bundle-gzip-detail',
    description: rows.map((row) => `${row.file} ${row.gzip} (raw ${row.raw})`).join('; '),
  });

  console.log(
    ['', `perf — dist/assets/*.js gzip total: ${total} bytes`]
      .concat(rows.map((row) => `  ${String(row.gzip).padStart(8)}  ${row.file}`))
      .join('\n'),
  );
  expect(rows.length, 'dist/assets holds at least one JS chunk').toBeGreaterThan(0);
});
