import AxeBuilder from '@axe-core/playwright';
import { expect, type Page } from '@playwright/test';
import { mkdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { isRecording } from './recorder';

/**
 * Accessibility baseline.
 *
 * Phase 0 does not fix anything — it writes down exactly which violations the
 * app ships today, per route, so a later phase can be held to "no new ones".
 *
 * ## Why the baseline is keyed by rule id and not by element
 *
 * axe identifies an offending element with a CSS selector it synthesises from
 * whatever the element has: on this app that is almost always a Tailwind class
 * chain (`.idx-0 > .card-inner > .card-body`) or a generated PrimeVue id
 * (`#pv_id_7`). Both are exactly what a restyle changes. A baseline keyed on
 * them would re-report all 73 of today's violations as brand-new the first time
 * a class list moves, which is the opposite of useful — the suite would cry
 * wolf on the very change it exists to watch.
 *
 * So the baseline records, per route, one entry per **rule**: its impact and
 * how many elements are currently failing it. A run fails when a rule appears
 * that the route has never had, or when a known rule's count goes up. The raw
 * selectors are still written to the file under `examples`, because a human
 * reading it needs somewhere to start looking — but nothing is ever compared
 * against them.
 *
 * axe-core schedules its own work on `setTimeout`, and this suite runs with a
 * paused fake clock, so the clock is resumed before the scan. It is *not*
 * re-paused: `checkA11y` is therefore always the last step of a test.
 */

/** One rule's standing on one route. */
export interface BaselineRule {
  impact: string | null;
  count: number;
  /** Human-facing only. Never compared — see the note above. */
  examples: string[];
}

export type RouteBaseline = Record<string, BaselineRule>;
export type Baseline = Record<string, RouteBaseline>;

/** How many example selectors are kept per rule. Enough to find it, not a dump. */
const MAX_EXAMPLES = 5;

const BASELINE_PATH = resolve(process.cwd(), 'e2e/golden/axe-baseline.json');

function readBaseline(): Baseline {
  if (!existsSync(BASELINE_PATH)) return {};
  return JSON.parse(readFileSync(BASELINE_PATH, 'utf8')) as Baseline;
}

function writeBaseline(baseline: Baseline): void {
  mkdirSync(resolve(process.cwd(), 'e2e/golden'), { recursive: true });
  const sorted: Baseline = {};
  for (const route of Object.keys(baseline).sort()) sorted[route] = baseline[route]!;
  writeFileSync(BASELINE_PATH, `${JSON.stringify(sorted, null, 2)}\n`);
}

/**
 * The regressions in `found` relative to `known`: a rule the route has never
 * reported, or a known rule now failing on more elements than it did.
 *
 * Pure, and exported so `axe.compare.spec.ts` can hold it to its own rules
 * without waiting on a browser.
 */
export function findRegressions(found: RouteBaseline, known: RouteBaseline): string[] {
  const regressions: string[] = [];
  for (const ruleId of Object.keys(found).sort()) {
    const now = found[ruleId]!;
    const before = known[ruleId];
    if (!before) {
      regressions.push(`${ruleId}: new rule (${now.count} element(s))`);
    } else if (now.count > before.count) {
      regressions.push(`${ruleId}: ${before.count} -> ${now.count} element(s)`);
    }
  }
  return regressions;
}

async function scan(page: Page): Promise<RouteBaseline> {
  await page.clock.resume();
  const results = await new AxeBuilder({ page }).analyze();

  const route: RouteBaseline = {};
  for (const violation of [...results.violations].sort((a, b) => a.id.localeCompare(b.id))) {
    const targets = violation.nodes
      .flatMap((node) => node.target.map((selector) => String(selector)))
      .sort();
    route[violation.id] = {
      impact: violation.impact ?? null,
      count: violation.nodes.length,
      examples: targets.slice(0, MAX_EXAMPLES),
    };
  }
  return route;
}

export async function checkA11y(page: Page, routeName: string): Promise<void> {
  const found = await scan(page);

  if (isRecording) {
    const baseline = readBaseline();
    baseline[routeName] = found;
    writeBaseline(baseline);
    return;
  }

  const known = readBaseline()[routeName];
  if (!known) {
    throw new Error(
      `No axe baseline for route "${routeName}". Record it with \`npm run e2e:record\`.`,
    );
  }

  expect(
    findRegressions(found, known),
    `new or worsened accessibility violations on "${routeName}"`,
  ).toEqual([]);
}
