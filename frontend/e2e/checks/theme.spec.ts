import { checkA11y, expect, test } from '../fixtures';

/**
 * Looks and modes, end to end: the first paint is the default look in the
 * default mode, the toggle and the picker apply instantly and persist across a
 * reload in *this* browser only, every `--chart-*` token resolves in all eight
 * look × mode sets, and axe passes each set on the dashboard and on the
 * liquidity page (baseline keys `<route>@<look>-<mode>`, recorded with
 * `npm run e2e:record`).
 *
 * Mirrors `src/design/looks.ts` and `theme.ts`: the ids, keys and defaults
 * are literal here on purpose, so a change there that forgot this spec fails.
 */

const LOOKS = ['obsidian', 'aurora', 'brutal', 'luxury'] as const;
const DEFAULT_LOOK = 'luxury';
const DEFAULT_DARK = true;

/** The display face each look declares, as it appears in the computed font-family. */
const DISPLAY_FACE: Record<(typeof LOOKS)[number], string> = {
  obsidian: 'JetBrains Mono',
  aurora: 'Space Grotesk',
  brutal: 'Unbounded',
  luxury: 'Fraunces',
};

const CHART_NAMES = [
  'bg', 'grid', 'axis-text', 'reserve-band', 'weekend-band', 'today-band', 'month-line', 'day-line',
  'month-label', 'day-today', 'day-hover', 'day-active', 'day-idle', 'marker-today', 'marker-idle',
  'today-line', 'net-positive', 'net-negative', 'inflow-fill-hover', 'inflow-fill', 'inflow-stroke-hover',
  'inflow-stroke', 'outflow-fill-hover', 'outflow-fill', 'outflow-stroke-hover', 'outflow-stroke',
  'reserve-line', 'baseline', 'balance-dot', 'balance-dot-core', 'min-negative', 'min-warning',
];

const COLOUR = /^(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))$/;

const rootState = (page: import('@playwright/test').Page) =>
  page.evaluate(() => ({
    look: document.documentElement.dataset.look,
    dark: document.documentElement.classList.contains('dark'),
    scheme: document.documentElement.style.colorScheme,
    bodyBg: getComputedStyle(document.body).backgroundColor,
    h1Font: getComputedStyle(document.querySelector('h1')!).fontFamily,
  }));

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium', 'token resolution is engine-independent; checked on chromium only');
});

test('a fresh browser paints the default look and mode before any script runs', async ({ page }) => {
  // Snapshot <html> at the earliest possible moment: the pre-paint script has
  // run, the app bundle has not.
  await page.addInitScript(() => {
    document.addEventListener('DOMContentLoaded', () => {
      (window as unknown as { __firstPaint: unknown }).__firstPaint = {
        look: document.documentElement.dataset.look,
        dark: document.documentElement.classList.contains('dark'),
      };
    });
  });
  await page.goto('/');
  await expect(page.getByTestId('landing.offer')).toBeVisible();
  const first = await page.evaluate(() => (window as unknown as { __firstPaint: unknown }).__firstPaint);
  expect(first).toEqual({ look: DEFAULT_LOOK, dark: DEFAULT_DARK });
  const now = await rootState(page);
  expect(now.look).toBe(DEFAULT_LOOK);
  expect(now.dark).toBe(DEFAULT_DARK);
  expect(now.scheme).toBe(DEFAULT_DARK ? 'dark' : 'light');
  expect(now.h1Font).toContain(DISPLAY_FACE[DEFAULT_LOOK]);
});

test('the mode toggle applies instantly and persists across a reload in this browser', async ({ page }) => {
  await page.goto('/');
  const before = await rootState(page);
  await page.getByTestId('shell.theme-toggle').click();
  await expect.poll(async () => (await rootState(page)).dark).toBe(!DEFAULT_DARK);
  // The ground cross-fades (CSS, `--dur-base`), so poll for the settled colour.
  await expect.poll(async () => (await rootState(page)).bodyBg).not.toBe(before.bodyBg);
  expect(await page.evaluate(() => localStorage.getItem('bw.theme'))).toBe(DEFAULT_DARK ? 'light' : 'dark');
  await page.reload();
  await expect(page.getByTestId('landing.offer')).toBeVisible();
  expect((await rootState(page)).dark).toBe(!DEFAULT_DARK);
});

test('every look applies from Settings, changes the display face, and persists', async ({ page, api }) => {
  await page.goto('/');
  for (const look of LOOKS) {
    await page.getByTestId('shell.settings-open').click();
    await page.getByTestId(`shell.look.${look}`).click();
    await expect(page.getByTestId(`shell.look.${look}`)).toHaveAttribute('aria-checked', 'true');
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('shell.settings')).toBeHidden();
    const state = await rootState(page);
    expect(state.look).toBe(look);
    expect(state.h1Font, look).toContain(DISPLAY_FACE[look]);
    expect(await page.evaluate(() => localStorage.getItem('bw.look'))).toBe(look);
  }
  await page.reload();
  await expect(page.getByTestId('landing.offer')).toBeVisible();
  expect((await rootState(page)).look).toBe(LOOKS[LOOKS.length - 1]);
  // The choice never left the browser: no request mentions a look or a key.
  const leaked = api.matching((request) => /bw\.(look|theme|motion)|obsidian|aurora|brutal|luxury/i.test(JSON.stringify(request)));
  expect(leaked).toEqual([]);
});

test('a second browser context starts from the defaults, whatever the first chose', async ({ page, browser }) => {
  await page.goto('/');
  await page.getByTestId('shell.settings-open').click();
  await page.getByTestId('shell.look.brutal').click();
  await page.keyboard.press('Escape');
  await page.getByTestId('shell.theme-toggle').click();
  expect((await rootState(page)).look).toBe('brutal');

  const other = await browser.newContext();
  const page2 = await other.newPage();
  await page2.goto('/');
  await expect(page2.getByTestId('landing.offer')).toBeVisible();
  const fresh = await rootState(page2);
  expect(fresh.look).toBe(DEFAULT_LOOK);
  expect(fresh.dark).toBe(DEFAULT_DARK);
  await other.close();
});

test('every --chart-* token resolves to a colour in all eight look × mode sets', async ({ page }) => {
  await page.goto('/liquidity');
  await expect(page.getByTestId('liquidity.add-flow')).toBeVisible();
  for (const look of LOOKS) {
    const bgByMode: string[] = [];
    for (const dark of [false, true]) {
      await page.evaluate(
        ([l, d]) => {
          localStorage.setItem('bw.look', l as string);
          localStorage.setItem('bw.theme', d ? 'dark' : 'light');
        },
        [look, dark] as const,
      );
      await page.reload();
      await expect(page.getByTestId('liquidity.add-flow')).toBeVisible();
      const state = await rootState(page);
      expect(state.look).toBe(look);
      expect(state.dark).toBe(dark);
      const resolved = await page.evaluate((names) => {
        const style = getComputedStyle(document.documentElement);
        return names.map((name) => style.getPropertyValue(`--chart-${name}`).trim());
      }, CHART_NAMES);
      resolved.forEach((value, i) => {
        expect(value, `${look}/${dark ? 'dark' : 'light'} --chart-${CHART_NAMES[i]}`).toMatch(COLOUR);
      });
      bgByMode.push(resolved[0]!);
    }
    // Light and dark are different palettes within a look (several looks share
    // a white light surface with each other, which is fine).
    expect(bgByMode[0], `${look}: light and dark --chart-bg`).not.toBe(bgByMode[1]);
  }
});

test.describe('axe in every look and mode', () => {
  for (const look of LOOKS) {
    for (const dark of [false, true]) {
      const mode = dark ? 'dark' : 'light';
      test(`dashboard and liquidity pass in ${look} ${mode}`, async ({ page }) => {
        await page.goto('/');
        await page.evaluate(
          ([l, d]) => {
            localStorage.setItem('bw.look', l as string);
            localStorage.setItem('bw.theme', d ? 'dark' : 'light');
          },
          [look, dark] as const,
        );
        await page.reload();
        await expect(page.getByTestId('landing.offer')).toBeVisible();
        expect((await rootState(page)).look).toBe(look);
        await checkA11y(page, `landing@${look}-${mode}`);
        await page.goto('/liquidity');
        await expect(page.getByTestId('liquidity.add-flow')).toBeVisible();
        await checkA11y(page, `liquidity@${look}-${mode}`);
      });
    }
  }

  test('the Appearance drawer itself passes', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('shell.settings-open').click();
    await expect(page.getByTestId('shell.settings')).toBeVisible();
    await checkA11y(page, 'settings@modal');
  });

  test('the command palette passes', async ({ page }) => {
    await page.goto('/');
    await page.keyboard.press('Control+k');
    await expect(page.getByTestId('shell.command')).toBeVisible();
    await checkA11y(page, 'command@modal');
  });
});
