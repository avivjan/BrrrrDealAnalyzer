import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { CHART_FALLBACKS, type ChartTokenName } from '../../src/design/chartTokens';
import { expect, test } from '../fixtures';

/**
 * The liquidity chart's palette, checked in a real browser.
 *
 * `TimelineChart.vue` draws on a `<canvas>`, which takes a resolved colour
 * string and silently ignores anything else — `ctx.fillStyle = 'bg-surface'`
 * is not an error, it is a no-op that leaves the previous colour in place. So
 * the 32 colours live in `tokens.css` as `--chart-*` literals and the chart
 * reads them through `chartToken()`.
 *
 * `chartToken()` never throws: a name the stylesheet does not answer falls
 * back to the dark literal the chart shipped with. That is the right runtime
 * behaviour and the wrong test behaviour — a typo'd or deleted token would
 * draw a dark-theme colour onto a light chart and nothing would fail. This
 * check is what makes that loud: it asks the browser for all 32 names and
 * requires every one of them to come back as a usable colour.
 *
 * Deterministic by construction: one navigation, then a `getComputedStyle`
 * read. Nothing here depends on the backend's data, only on the page loading.
 * chromium only — CSS custom-property resolution is not engine-specific, and
 * three more copies of the same read would only slow the suite down.
 */

const NAMES = Object.keys(CHART_FALLBACKS) as ChartTokenName[];

/** What a `<canvas>` accepts: `#rgb`…`#rrggbbaa`, `rgb(…)`, `rgba(…)`. */
const COLOUR = /^(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))$/;

/**
 * One spelling per colour, so a comparison survives the build.
 *
 * A custom property is not computed — the browser hands back the token stream
 * it was given — but the *bundler* minifies the stylesheet on the way there:
 * `rgba(220, 38, 38, 0.06)` is served as `rgba(220,38,38,.06)`, and a short
 * hex may lose its repeats. Both sides go through this before they are
 * compared, so the check tests the palette rather than the minifier.
 */
const canonical = (value: string): string => {
  const compact = value.toLowerCase().replace(/\s+/g, '').replace(/(^|[^0-9])\./g, '$10.');
  const short = /^#([0-9a-f])([0-9a-f])([0-9a-f])([0-9a-f])?$/.exec(compact);
  return short
    ? `#${short
        .slice(1)
        .filter(Boolean)
        .map((channel) => channel + channel)
        .join('')}`
    : compact;
};

/**
 * The `--chart-*` values `tokens.css` declares on `:root` — the light palette.
 *
 * This is what turns "something resolved" into "the palette this repository
 * ships resolved", which is the part `chartToken()`'s silent fallback would
 * otherwise hide.
 */
const declaredOnRoot = (() => {
  const css = readFileSync(resolve(process.cwd(), 'src/assets/tokens.css'), 'utf8');
  const start = css.indexOf(':root {');
  const block = css.slice(start, css.indexOf('\n}', start));
  const found: Record<string, string> = {};
  for (const match of block.matchAll(/--chart-([a-z0-9-]+)\s*:\s*([^;]+);/g)) {
    found[match[1]!] = match[2]!.trim();
  }
  return found;
})();

test.beforeEach(({}, testInfo) => {
  test.skip(
    testInfo.project.name !== 'chromium',
    'custom-property resolution is engine-independent; checked on chromium only',
  );
});

test('every --chart-* token resolves to a colour on /liquidity', async ({ page }) => {
  await page.goto('/liquidity');
  await expect(page.getByTestId('liquidity.add-flow')).toBeVisible();

  const resolved = await page.evaluate((names) => {
    const style = getComputedStyle(document.documentElement);
    return Object.fromEntries(
      names.map((name) => [name, style.getPropertyValue(`--chart-${name}`).trim()]),
    ) as Record<string, string>;
  }, NAMES as string[]);

  expect(Object.keys(resolved).sort()).toEqual([...NAMES].sort());

  const unresolved = NAMES.filter((name) => resolved[name] === '');
  expect(unresolved, 'chart tokens the stylesheet does not declare').toEqual([]);

  const notAColour = NAMES.filter((name) => !COLOUR.test(resolved[name]!));
  expect(
    notAColour.map((name) => `${name}: ${resolved[name]}`),
    'chart tokens a <canvas> would silently ignore',
  ).toEqual([]);

  // Every name resolves to the value `:root` declares — so the browser is
  // answering from the stylesheet, not from `chartToken()`'s dark fallbacks.
  for (const name of NAMES) {
    expect(canonical(resolved[name] ?? ''), `--chart-${name}`).toBe(
      canonical(declaredOnRoot[name] ?? ''),
    );
  }
});
