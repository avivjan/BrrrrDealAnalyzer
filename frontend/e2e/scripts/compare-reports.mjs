#!/usr/bin/env node
/**
 * `npm run e2e:compare` — the Phase 0 vs Phase 5 proof.
 *
 * Compares two Playwright JSON reports test-by-test and fails when the
 * overhaul lost behaviour. Tests are matched on
 * `(projectName, spec file, title path)` and never on the report's absolute
 * `file` / `rootDir` values, because the archived Phase 0 report was written
 * by a reporter that recorded machine-specific paths.
 *
 * The rules, in the order they are applied:
 *
 *   - a test that PASSED in `before` must PASS in `after` (skipping it,
 *     failing it or deleting it is a regression);
 *   - a test that was SKIPPED in `before` may PASS or stay SKIPPED in
 *     `after` (skipped -> passed is a superset, so it is listed, not failed);
 *   - a test present only in `after` is an addition and is listed, unless it
 *     failed;
 *   - any failed / flaky test in `after` is a failure;
 *   - a project `after` did not run at all (a narrower `--project` matrix) is
 *     reported as out-of-matrix and its tests are not compared; a test missing
 *     from a project `after` *did* run is a deletion, and fails.
 *
 * Usage: node e2e/scripts/compare-reports.mjs <before.json> <after.json>
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/** Playwright's per-test status vocabulary, mapped onto ours. */
export const STATUS_BY_PLAYWRIGHT = Object.freeze({
  expected: 'passed',
  unexpected: 'failed',
  flaky: 'flaky',
  skipped: 'skipped',
});

/** Statuses that fail the comparison whatever the other side says. */
export const BAD_STATUSES = Object.freeze(['failed', 'flaky', 'unknown']);

/**
 * Reduce a report's `file` to something stable across machines: relative to
 * `rootDir` when it sits under it, else the part after the last `/e2e/`, else
 * the basename. Never returns an absolute path.
 */
export function normalizeFile(file, rootDir = '') {
  if (!file) return '';
  const path = String(file).replace(/\\/g, '/');
  const root = String(rootDir ?? '')
    .replace(/\\/g, '/')
    .replace(/\/+$/, '');
  if (root && path.startsWith(`${root}/`)) return path.slice(root.length + 1);
  if (!/^(\/|[A-Za-z]:\/)/.test(path)) return path.replace(/^\.\//, '');
  const marker = path.lastIndexOf('/e2e/');
  if (marker !== -1) return path.slice(marker + '/e2e/'.length);
  return path.slice(path.lastIndexOf('/') + 1);
}

/** One test's outcome, tolerating reports that only carry result statuses. */
export function statusOf(test) {
  const mapped = STATUS_BY_PLAYWRIGHT[test?.status];
  if (mapped) return mapped;
  const results = test?.results ?? [];
  const raw = results[results.length - 1]?.status;
  if (raw === 'passed') return 'passed';
  if (raw === 'skipped') return 'skipped';
  return raw ? 'failed' : 'unknown';
}

/** The identity of a test across two runs. */
export function testKey({ project, file, title }) {
  return `${project} :: ${file} :: ${title}`;
}

/** Human form of a test, for the printed lists. */
export function describeTest({ project, file, title }) {
  return `[${project}] ${file} > ${title}`;
}

/**
 * Flatten a Playwright JSON report to `key -> {project, file, title, status}`.
 * The per-file suite (whose `title` *is* its `file`) contributes nothing to the
 * title path; nested `describe` suites do.
 */
export function collectTests(report) {
  const rootDir = report?.config?.rootDir ?? '';
  const tests = new Map();

  const walk = (suite, titles, inheritedFile) => {
    const file = suite?.file ?? inheritedFile;
    const isFileSuite = !suite?.title || suite.title === suite.file;
    const path = isFileSuite ? titles : [...titles, suite.title];
    for (const spec of suite?.specs ?? []) {
      const specFile = normalizeFile(spec.file ?? file, rootDir);
      const title = [...path, spec.title].join(' > ');
      for (const test of spec.tests ?? []) {
        const entry = {
          project: test.projectName ?? test.projectId ?? '',
          file: specFile,
          title,
          status: statusOf(test),
        };
        tests.set(testKey(entry), entry);
      }
    }
    for (const child of suite?.suites ?? []) walk(child, path, file);
  };

  for (const suite of report?.suites ?? []) walk(suite, [], undefined);
  return tests;
}

function projectsOf(tests) {
  return new Set([...tests.values()].map((test) => test.project));
}

/** Apply the rules in the module docblock to two parsed reports. */
export function compareReports(beforeReport, afterReport) {
  const before = collectTests(beforeReport);
  const after = collectTests(afterReport);
  const beforeProjects = projectsOf(before);
  const afterProjects = projectsOf(after);
  const outOfMatrixProjects = [...beforeProjects]
    .filter((project) => !afterProjects.has(project))
    .sort();

  const result = {
    beforeCount: before.size,
    afterCount: after.size,
    beforeProjects: [...beforeProjects].sort(),
    afterProjects: [...afterProjects].sort(),
    outOfMatrixProjects,
    passedToPassed: 0,
    skippedToSkipped: 0,
    skippedToPassed: [],
    recovered: [],
    additions: [],
    outOfMatrix: [],
    failures: [],
    ok: true,
  };

  const fail = (kind, entry, detail) => result.failures.push({ kind, ...entry, detail });

  for (const [key, entry] of before) {
    if (outOfMatrixProjects.includes(entry.project)) {
      result.outOfMatrix.push(entry);
      continue;
    }
    const now = after.get(key);
    if (!now) {
      fail('removed', entry, `${entry.status} in before, absent from after`);
      continue;
    }
    if (BAD_STATUSES.includes(now.status)) {
      fail('failed', entry, `${entry.status} -> ${now.status}`);
      continue;
    }
    if (entry.status === 'passed') {
      if (now.status === 'passed') result.passedToPassed += 1;
      else fail('coverage-lost', entry, `passed -> ${now.status}`);
    } else if (entry.status === 'skipped') {
      if (now.status === 'passed') result.skippedToPassed.push(entry);
      else result.skippedToSkipped += 1;
    } else if (now.status === 'passed') {
      result.recovered.push({ ...entry, detail: `${entry.status} -> passed` });
    } else {
      fail('coverage-lost', entry, `${entry.status} -> ${now.status}`);
    }
  }

  for (const [key, entry] of after) {
    if (before.has(key)) continue;
    if (BAD_STATUSES.includes(entry.status)) fail('new-test-failed', entry, entry.status);
    else result.additions.push(entry);
  }

  result.ok = result.failures.length === 0;
  return result;
}

function row(label, count) {
  return `  ${label.padEnd(34)}${String(count).padStart(5)}`;
}

function section(lines, heading, entries, render = describeTest) {
  if (entries.length === 0) return;
  lines.push('');
  lines.push(`${heading} (${entries.length}):`);
  for (const entry of entries) lines.push(`  ${render(entry)}`);
}

/** The printed report, as an array of lines. */
export function formatSummary(result, beforeLabel = 'before', afterLabel = 'after') {
  const lines = [
    'Playwright report comparison',
    `  ${beforeLabel}: ${result.beforeCount} tests, projects: ${result.beforeProjects.join(', ')}`,
    `  ${afterLabel}: ${result.afterCount} tests, projects: ${result.afterProjects.join(', ')}`,
    '',
    `  ${'outcome'.padEnd(34)}${'count'.padStart(5)}`,
    `  ${'-'.repeat(34)}${'-'.repeat(5)}`,
    row('passed -> passed', result.passedToPassed),
    row('skipped -> passed', result.skippedToPassed.length),
    row('skipped -> skipped', result.skippedToSkipped),
    row('recovered (was not passing)', result.recovered.length),
    row('added in after', result.additions.length),
    row('out of matrix (not compared)', result.outOfMatrix.length),
    row('failures', result.failures.length),
  ];

  section(lines, 'skipped -> passed', result.skippedToPassed);
  section(lines, 'recovered', result.recovered, (entry) => `${describeTest(entry)} (${entry.detail})`);
  section(lines, 'added in after', result.additions, (entry) => `${describeTest(entry)} (${entry.status})`);
  section(
    lines,
    `out of matrix -- projects not run in after: ${result.outOfMatrixProjects.join(', ')}`,
    result.outOfMatrix,
    (entry) => `${describeTest(entry)} (${entry.status} in before)`,
  );
  section(
    lines,
    'FAILURES',
    result.failures,
    (entry) => `${entry.kind}: ${describeTest(entry)} -- ${entry.detail}`,
  );

  lines.push('');
  lines.push(result.ok ? 'compare-reports PASS' : 'compare-reports FAIL');
  return lines;
}

function readReport(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

/** CLI body; returns the exit code so the unit test can drive it. */
export function main(argv, log = console.log) {
  const [beforePath, afterPath] = argv;
  if (!beforePath || !afterPath) {
    log('usage: node e2e/scripts/compare-reports.mjs <before.json> <after.json>');
    return 2;
  }
  const result = compareReports(readReport(beforePath), readReport(afterPath));
  for (const line of formatSummary(result, beforePath, afterPath)) log(line);
  return result.ok ? 0 : 1;
}

if (process.argv[1] !== undefined && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = main(process.argv.slice(2));
}
