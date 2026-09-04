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
 * A violation is identified by its rule id plus the element selectors it fired
 * on; anything not already in the baseline fails.
 *
 * axe-core schedules its own work on `setTimeout`, and this suite runs with a
 * paused fake clock, so the clock is resumed before the scan. It is *not*
 * re-paused: `checkA11y` is therefore always the last step of a test.
 */

export interface AxeViolation {
  id: string;
  impact: string | null;
  targets: string[];
}

const BASELINE_PATH = resolve(process.cwd(), 'e2e/golden/axe-baseline.json');

type Baseline = Record<string, AxeViolation[]>;

function readBaseline(): Baseline {
  if (!existsSync(BASELINE_PATH)) return {};
  return JSON.parse(readFileSync(BASELINE_PATH, 'utf8')) as Baseline;
}

function writeBaseline(baseline: Baseline): void {
  mkdirSync(resolve(process.cwd(), 'e2e/golden'), { recursive: true });
  const sorted: Baseline = {};
  for (const key of Object.keys(baseline).sort()) sorted[key] = baseline[key]!;
  writeFileSync(BASELINE_PATH, `${JSON.stringify(sorted, null, 2)}\n`);
}

/** `{ id, impact, targets }`, sorted, so the file diffs meaningfully. */
async function scan(page: Page): Promise<AxeViolation[]> {
  await page.clock.resume();
  const results = await new AxeBuilder({ page }).analyze();
  return results.violations
    .map((violation) => ({
      id: violation.id,
      impact: violation.impact ?? null,
      targets: violation.nodes
        .flatMap((node) => node.target.map((selector) => String(selector)))
        .sort(),
    }))
    .sort((a, b) => a.id.localeCompare(b.id));
}

export async function checkA11y(page: Page, routeName: string): Promise<void> {
  const found = await scan(page);

  if (isRecording) {
    const baseline = readBaseline();
    baseline[routeName] = found;
    writeBaseline(baseline);
    return;
  }

  const baseline = readBaseline();
  const known = baseline[routeName];
  if (!known) {
    throw new Error(
      `No axe baseline for route "${routeName}". Record it with \`npm run e2e:record\`.`,
    );
  }

  const knownTargets = new Set(
    known.flatMap((violation) => violation.targets.map((t) => `${violation.id} :: ${t}`)),
  );
  const regressions = found.flatMap((violation) =>
    violation.targets
      .map((t) => `${violation.id} :: ${t}`)
      .filter((key) => !knownTargets.has(key)),
  );

  expect(regressions, `new accessibility violations on "${routeName}"`).toEqual([]);
}
