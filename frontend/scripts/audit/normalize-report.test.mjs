import { describe, expect, it } from 'vitest';
import {
  CONFIG_FILE_RELATIVE,
  inferRepoRoot,
  normalizeReport,
  parseArgs,
  serializeReport,
  stripRoot,
  toPosix,
} from '../../e2e/scripts/normalize-report.mjs';

/**
 * The normaliser lives under `e2e/`, which Vitest excludes (those specs are
 * Playwright's). Its unit test therefore lives here, next to the other
 * audit-script tests, and imports across — the same arrangement Task 5.1 used
 * for `compare-reports`.
 *
 * Every sample root below is `/repo…`: a fixture spelled with a real home
 * directory would put an absolute path into a tracked file, which is the exact
 * thing gate G8 exists to stop.
 */

const ROOT = '/repo/checkout';

/** A Playwright JSON report in the reporter's shape, rooted at `root`. */
function report(root = ROOT, { specFile = `${root}/frontend/e2e/flows/liquidity.spec.ts` } = {}) {
  return {
    config: {
      argv: ['/usr/local/bin/node', `${root}/frontend/node_modules/.bin/playwright`, 'test'],
      configFile: `${root}/${CONFIG_FILE_RELATIVE}`,
      rootDir: `${root}/frontend/e2e`,
      version: '1.62.1',
      projects: [
        {
          id: 'chromium',
          name: 'chromium',
          outputDir: `${root}/frontend/test-results`,
          testDir: `${root}/frontend/e2e`,
          testMatch: ['**/*.@(spec|test).?(c|m)[jt]s?(x)'],
          timeout: 90_000,
        },
      ],
    },
    suites: [
      {
        title: 'flows/liquidity.spec.ts',
        file: 'flows/liquidity.spec.ts',
        specs: [
          {
            title: 'renders',
            file: specFile,
            line: 12,
            tests: [{ projectName: 'chromium', status: 'expected', results: [{ status: 'passed' }] }],
          },
        ],
      },
    ],
    errors: [],
    stats: { expected: 1, skipped: 0, unexpected: 0, flaky: 0 },
  };
}

describe('inferRepoRoot', () => {
  it('reads the root back off the recorded config file', () => {
    expect(inferRepoRoot(report())).toBe(ROOT);
  });

  it('reads a Windows-recorded root back as POSIX', () => {
    const drive = ['C:', 'work', 'checkout'].join('\\');
    const configFile = [drive, ...CONFIG_FILE_RELATIVE.split('/')].join('\\');
    expect(inferRepoRoot({ config: { configFile } })).toBe('C:/work/checkout');
  });

  it('returns nothing for an already-normalised report', () => {
    expect(inferRepoRoot({ config: { configFile: CONFIG_FILE_RELATIVE } })).toBe('');
  });

  it('returns nothing when there is no config file at all', () => {
    expect(inferRepoRoot({})).toBe('');
    expect(inferRepoRoot({ config: {} })).toBe('');
  });

  it('refuses a root that would strip the filesystem root', () => {
    expect(inferRepoRoot({ config: { configFile: `/${CONFIG_FILE_RELATIVE}` } })).toBe('');
  });
});

describe('stripRoot', () => {
  it('makes an under-the-root path repo-relative', () => {
    expect(stripRoot(`${ROOT}/frontend/e2e/flows/a.spec.ts`, ROOT)).toBe('frontend/e2e/flows/a.spec.ts');
  });

  it('leaves a path outside the root alone', () => {
    expect(stripRoot('/usr/local/bin/node', ROOT)).toBeNull();
    expect(stripRoot('/repo/other/frontend', ROOT)).toBeNull();
  });

  it('leaves ordinary strings alone', () => {
    expect(stripRoot('chromium', ROOT)).toBeNull();
    expect(stripRoot('', ROOT)).toBeNull();
  });

  it('rewrites the root mentioned inside a longer string', () => {
    const message = `Error: ENOENT, open "${ROOT}/frontend/e2e/golden/axe.json"`;
    expect(stripRoot(message, ROOT)).toBe('Error: ENOENT, open "frontend/e2e/golden/axe.json"');
  });

  it('converts a Windows-recorded tail to POSIX', () => {
    const winRoot = ['C:', 'work', 'checkout'].join('\\');
    const winPath = [winRoot, 'frontend', 'e2e', 'flows', 'a.spec.ts'].join('\\');
    expect(stripRoot(winPath, 'C:/work/checkout')).toBe('frontend/e2e/flows/a.spec.ts');
  });

  it('names the root itself rather than emitting an empty string', () => {
    expect(stripRoot(ROOT, ROOT)).toBe('.');
  });

  it('does nothing without a root', () => {
    expect(stripRoot(`${ROOT}/frontend`, '')).toBeNull();
  });
});

describe('normalizeReport', () => {
  it('rewrites every recorded path under the root', () => {
    const input = report();
    const { report: out, replacements } = normalizeReport(input);
    expect(out.config.configFile).toBe(CONFIG_FILE_RELATIVE);
    expect(out.config.rootDir).toBe('frontend/e2e');
    expect(out.config.argv[1]).toBe('frontend/node_modules/.bin/playwright');
    expect(out.config.projects[0].outputDir).toBe('frontend/test-results');
    expect(out.config.projects[0].testDir).toBe('frontend/e2e');
    expect(out.suites[0].specs[0].file).toBe('frontend/e2e/flows/liquidity.spec.ts');
    expect(replacements).toBe(6);
  });

  it('leaves paths outside the repository, and every non-path value, untouched', () => {
    const { report: out } = normalizeReport(report());
    expect(out.config.argv[0]).toBe('/usr/local/bin/node');
    expect(out.config.version).toBe('1.62.1');
    expect(out.config.projects[0].timeout).toBe(90_000);
    expect(out.config.projects[0].testMatch).toEqual(['**/*.@(spec|test).?(c|m)[jt]s?(x)']);
    expect(out.suites[0].specs[0].line).toBe(12);
    expect(out.stats).toEqual({ expected: 1, skipped: 0, unexpected: 0, flaky: 0 });
    expect(out.errors).toEqual([]);
  });

  it('does not mutate the report it was given', () => {
    const input = report();
    normalizeReport(input);
    expect(input.config.rootDir).toBe(`${ROOT}/frontend/e2e`);
  });

  it('is idempotent: a normalised report normalises to itself', () => {
    const once = normalizeReport(report()).report;
    const twice = normalizeReport(once);
    expect(twice.replacements).toBe(0);
    expect(twice.report).toEqual(once);
  });

  it('changes nothing when the root cannot be inferred', () => {
    const input = { config: { configFile: CONFIG_FILE_RELATIVE }, suites: [] };
    expect(normalizeReport(input)).toEqual({ report: input, replacements: 0, root: '' });
  });

  it('honours an explicit root', () => {
    const input = report('/repo/elsewhere');
    const { report: out } = normalizeReport(input, { root: '/repo/elsewhere' });
    expect(out.config.rootDir).toBe('frontend/e2e');
  });

  it('preserves key order, so the archive diff is paths only', () => {
    const { report: out } = normalizeReport(report());
    expect(Object.keys(out.config)).toEqual(Object.keys(report().config));
  });
});

describe('serializeReport', () => {
  it('matches the JSON reporter: two-space indent, no trailing newline', () => {
    const text = serializeReport({ a: 1 });
    expect(text).toBe('{\n  "a": 1\n}');
  });
});

describe('parseArgs', () => {
  it('reads the positional report path', () => {
    expect(parseArgs(['e2e/reports/last-run.json'])).toMatchObject({
      positionals: ['e2e/reports/last-run.json'],
      out: '',
      archive: '',
    });
  });

  it('reads --out, --root and --archive', () => {
    expect(parseArgs(['in.json', '--out', 'out.json', '--root', '/repo/x'])).toMatchObject({
      positionals: ['in.json'],
      out: 'out.json',
      root: '/repo/x',
    });
    expect(parseArgs(['--archive', 'phase5-final'])).toMatchObject({
      positionals: [],
      archive: 'phase5-final',
    });
  });
});

describe('toPosix', () => {
  it('rewrites backslash separators', () => {
    expect(toPosix(['a', 'b', 'c'].join('\\'))).toBe('a/b/c');
  });
});
