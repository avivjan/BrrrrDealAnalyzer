import { describe, expect, it } from 'vitest';
import {
  collectTests,
  compareReports,
  formatSummary,
  main,
  normalizeFile,
  statusOf,
  testKey,
} from '../../e2e/scripts/compare-reports.mjs';

/**
 * The comparison script lives under `e2e/`, which Vitest excludes (those specs
 * are Playwright's). Its unit test therefore lives here, next to the other
 * audit-script tests, and imports across.
 */

/** A Playwright JSON report with one spec per entry, in the reporter's shape. */
function report(entries, { rootDir = '/repo/frontend/e2e' } = {}) {
  const byFile = new Map();
  for (const entry of entries) {
    const file = entry.file ?? 'flows/demo.spec.ts';
    if (!byFile.has(file)) byFile.set(file, []);
    byFile.get(file).push(entry);
  }
  return {
    config: { rootDir },
    suites: [...byFile].map(([file, specs]) => ({
      title: file,
      file,
      specs: specs.map((entry) => ({
        title: entry.title,
        file: entry.specFile ?? file,
        tests: [{ projectName: entry.project, status: entry.status }],
      })),
    })),
  };
}

const passed = (project, title, extra = {}) => ({ project, title, status: 'expected', ...extra });
const skipped = (project, title, extra = {}) => ({ project, title, status: 'skipped', ...extra });
const failed = (project, title, extra = {}) => ({ project, title, status: 'unexpected', ...extra });

describe('normalizeFile', () => {
  it('keeps an already-relative path unchanged', () => {
    expect(normalizeFile('flows/landing.spec.ts')).toBe('flows/landing.spec.ts');
  });

  it('strips a leading ./', () => {
    expect(normalizeFile('./flows/landing.spec.ts')).toBe('flows/landing.spec.ts');
  });

  it('makes an absolute path relative to rootDir', () => {
    expect(normalizeFile('/a/b/e2e/flows/landing.spec.ts', '/a/b/e2e')).toBe(
      'flows/landing.spec.ts',
    );
  });

  it('tolerates a trailing slash on rootDir', () => {
    expect(normalizeFile('/a/b/e2e/flows/landing.spec.ts', '/a/b/e2e/')).toBe(
      'flows/landing.spec.ts',
    );
  });

  it('falls back to the part after the last /e2e/ when rootDir does not match', () => {
    expect(normalizeFile('/other/machine/e2e/flows/landing.spec.ts', '/a/b/e2e')).toBe(
      'flows/landing.spec.ts',
    );
  });

  it('falls back to the basename when there is no /e2e/ segment', () => {
    expect(normalizeFile('/x/y/landing.spec.ts', '/a/b')).toBe('landing.spec.ts');
  });

  it('normalises windows separators', () => {
    expect(normalizeFile('C:\\a\\e2e\\flows\\landing.spec.ts')).toBe('flows/landing.spec.ts');
  });

  it('returns an empty string for a missing file', () => {
    expect(normalizeFile(undefined)).toBe('');
  });

  it('never returns an absolute path', () => {
    for (const input of ['/a/e2e/f.spec.ts', '/a/f.spec.ts', 'C:/a/f.spec.ts']) {
      expect(normalizeFile(input).startsWith('/')).toBe(false);
    }
  });
});

describe('statusOf', () => {
  it('maps playwright test statuses', () => {
    expect(statusOf({ status: 'expected' })).toBe('passed');
    expect(statusOf({ status: 'unexpected' })).toBe('failed');
    expect(statusOf({ status: 'flaky' })).toBe('flaky');
    expect(statusOf({ status: 'skipped' })).toBe('skipped');
  });

  it('falls back to the last result when the test carries no status', () => {
    expect(statusOf({ results: [{ status: 'failed' }, { status: 'passed' }] })).toBe('passed');
    expect(statusOf({ results: [{ status: 'timedOut' }] })).toBe('failed');
    expect(statusOf({ results: [{ status: 'skipped' }] })).toBe('skipped');
  });

  it('reports unknown when there is nothing to go on', () => {
    expect(statusOf({})).toBe('unknown');
    expect(statusOf(undefined)).toBe('unknown');
  });
});

describe('collectTests', () => {
  it('keys on project, file and title', () => {
    const tests = collectTests(report([passed('chromium', 'lands')]));
    expect([...tests.keys()]).toEqual([
      testKey({ project: 'chromium', file: 'flows/demo.spec.ts', title: 'lands' }),
    ]);
    expect([...tests.values()][0].status).toBe('passed');
  });

  it('does not repeat the file name in the title path', () => {
    const tests = collectTests(report([passed('chromium', 'lands')]));
    expect([...tests.values()][0].title).toBe('lands');
  });

  it('includes nested describe titles in the title path', () => {
    const nested = {
      config: { rootDir: '/repo/frontend/e2e' },
      suites: [
        {
          title: 'flows/demo.spec.ts',
          file: 'flows/demo.spec.ts',
          specs: [],
          suites: [
            {
              title: 'a group',
              file: 'flows/demo.spec.ts',
              specs: [
                {
                  title: 'lands',
                  file: 'flows/demo.spec.ts',
                  tests: [{ projectName: 'chromium', status: 'expected' }],
                },
              ],
            },
          ],
        },
      ],
    };
    expect([...collectTests(nested).values()][0].title).toBe('a group > lands');
  });

  it('matches the same test across reports whose paths are absolute in one', () => {
    const relative = collectTests(report([passed('chromium', 'lands')]));
    const absolute = collectTests(
      report([passed('chromium', 'lands', { specFile: '/elsewhere/e2e/flows/demo.spec.ts' })], {
        rootDir: '/elsewhere/e2e',
      }),
    );
    expect([...absolute.keys()]).toEqual([...relative.keys()]);
  });

  it('returns an empty map for an empty report', () => {
    expect(collectTests({}).size).toBe(0);
  });
});

describe('compareReports', () => {
  it('passes when every passing test still passes', () => {
    const result = compareReports(
      report([passed('chromium', 'a'), passed('webkit', 'a')]),
      report([passed('chromium', 'a'), passed('webkit', 'a')]),
    );
    expect(result.ok).toBe(true);
    expect(result.passedToPassed).toBe(2);
    expect(result.failures).toEqual([]);
  });

  it('fails when a passing test now fails', () => {
    const result = compareReports(report([passed('chromium', 'a')]), report([failed('chromium', 'a')]));
    expect(result.ok).toBe(false);
    expect(result.failures).toHaveLength(1);
    expect(result.failures[0].kind).toBe('failed');
    expect(result.failures[0].detail).toBe('passed -> failed');
  });

  it('fails a flaky test in the after report', () => {
    const result = compareReports(
      report([passed('chromium', 'a')]),
      report([{ project: 'chromium', title: 'a', status: 'flaky' }]),
    );
    expect(result.ok).toBe(false);
    expect(result.failures[0].detail).toBe('passed -> flaky');
  });

  it('fails when a passing test is now skipped', () => {
    const result = compareReports(
      report([passed('chromium', 'a')]),
      report([skipped('chromium', 'a')]),
    );
    expect(result.ok).toBe(false);
    expect(result.failures[0].kind).toBe('coverage-lost');
  });

  it('fails when a passing test disappeared from a project that did run', () => {
    const result = compareReports(
      report([passed('chromium', 'a'), passed('chromium', 'b')]),
      report([passed('chromium', 'a')]),
    );
    expect(result.ok).toBe(false);
    expect(result.failures[0].kind).toBe('removed');
    expect(result.failures[0].title).toBe('b');
  });

  it('allows skipped -> passed and lists it', () => {
    const result = compareReports(
      report([skipped('Mobile Chrome', 'a')]),
      report([passed('Mobile Chrome', 'a')]),
    );
    expect(result.ok).toBe(true);
    expect(result.skippedToPassed.map((entry) => entry.title)).toEqual(['a']);
  });

  it('allows skipped -> skipped', () => {
    const result = compareReports(
      report([skipped('chromium', 'a')]),
      report([skipped('chromium', 'a')]),
    );
    expect(result.ok).toBe(true);
    expect(result.skippedToSkipped).toBe(1);
  });

  it('fails when a skipped test now fails', () => {
    const result = compareReports(
      report([skipped('chromium', 'a')]),
      report([failed('chromium', 'a')]),
    );
    expect(result.ok).toBe(false);
  });

  it('lists tests new in after as additions, not failures', () => {
    const result = compareReports(
      report([passed('chromium', 'a')]),
      report([passed('chromium', 'a'), passed('chromium', 'new', { file: 'checks/new.spec.ts' })]),
    );
    expect(result.ok).toBe(true);
    expect(result.additions.map((entry) => entry.file)).toEqual(['checks/new.spec.ts']);
  });

  it('fails a new test that failed', () => {
    const result = compareReports(
      report([passed('chromium', 'a')]),
      report([passed('chromium', 'a'), failed('chromium', 'new')]),
    );
    expect(result.ok).toBe(false);
    expect(result.failures[0].kind).toBe('new-test-failed');
  });

  it('reports a project the after run did not cover as out of matrix, not a failure', () => {
    const result = compareReports(
      report([passed('chromium', 'a'), passed('chromium-motion', 'm')]),
      report([passed('chromium', 'a')]),
    );
    expect(result.ok).toBe(true);
    expect(result.outOfMatrixProjects).toEqual(['chromium-motion']);
    expect(result.outOfMatrix.map((entry) => entry.title)).toEqual(['m']);
    expect(result.passedToPassed).toBe(1);
  });

  it('records the project lists and test counts of both sides', () => {
    const result = compareReports(
      report([passed('webkit', 'a'), passed('chromium', 'a')]),
      report([passed('webkit', 'a'), passed('chromium', 'a')]),
    );
    expect(result.beforeProjects).toEqual(['chromium', 'webkit']);
    expect(result.afterProjects).toEqual(['chromium', 'webkit']);
    expect(result.beforeCount).toBe(2);
    expect(result.afterCount).toBe(2);
  });

  it('lists a test that was failing before and passes now as recovered', () => {
    const result = compareReports(
      report([failed('chromium', 'a')]),
      report([passed('chromium', 'a')]),
    );
    expect(result.ok).toBe(true);
    expect(result.recovered).toHaveLength(1);
  });
});

describe('formatSummary', () => {
  it('prints the counts table and a PASS verdict', () => {
    const result = compareReports(report([passed('chromium', 'a')]), report([passed('chromium', 'a')]));
    const lines = formatSummary(result, 'phase0.json', 'phase5.json');
    expect(lines[0]).toBe('Playwright report comparison');
    expect(lines.join('\n')).toContain('phase0.json: 1 tests');
    expect(lines.some((line) => /passed -> passed\s+1$/.test(line))).toBe(true);
    expect(lines.at(-1)).toBe('compare-reports PASS');
  });

  it('prints every failure with its kind and a FAIL verdict', () => {
    const result = compareReports(report([passed('chromium', 'a')]), report([failed('chromium', 'a')]));
    const text = formatSummary(result).join('\n');
    expect(text).toContain('FAILURES (1):');
    expect(text).toContain('failed: [chromium] flows/demo.spec.ts > a -- passed -> failed');
    expect(text.endsWith('compare-reports FAIL')).toBe(true);
  });

  it('names the out-of-matrix projects in its heading', () => {
    const result = compareReports(
      report([passed('chromium', 'a'), passed('chromium-motion', 'm')]),
      report([passed('chromium', 'a')]),
    );
    expect(formatSummary(result).join('\n')).toContain(
      'out of matrix -- projects not run in after: chromium-motion (1)',
    );
  });

  it('omits sections that have no entries', () => {
    const result = compareReports(report([passed('chromium', 'a')]), report([passed('chromium', 'a')]));
    const text = formatSummary(result).join('\n');
    expect(text).not.toContain('FAILURES');
    expect(text).not.toContain('added in after (');
  });
});

describe('main', () => {
  it('returns 2 and prints usage when an argument is missing', () => {
    const lines = [];
    expect(main(['only-one.json'], (line) => lines.push(line))).toBe(2);
    expect(lines[0]).toContain('usage:');
  });
});
