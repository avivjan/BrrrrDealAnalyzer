import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
  ABSOLUTE_PATH_RULES,
  BINARY_EXTENSIONS,
  excerpt,
  isSkipped,
  run,
  scanText,
  summarize,
} from './paths.mjs';

/**
 * Every offending sample below is assembled from fragments rather than written
 * out. That is not decoration: this test file is itself a tracked file that gate
 * G8 scans, so a literal home-directory path here would fail the gate it tests
 * — and, worse, would make the repo-wide grep that answers "is anything left?"
 * report a hit forever.
 */

/** An absolute POSIX path, built so the literal never appears in this file. */
const abs = (...segments) => `/${segments.join('/')}`;
/** A Windows path, same reasoning. */
const win = (...segments) => segments.join('\\');

/** One backslash, kept out of the samples' source text for the same reason. */
const BACKSLASH = String.fromCharCode(92);

const HOME_MAC = abs('Users', 'alice', 'secrets', 'reps-writer.json');
const HOME_LINUX = abs('home', 'alice', 'repo', 'frontend');
const DRIVE = win('C:', 'work', 'repo', 'frontend');
const PRIVATE_TMP = abs('private', 'tmp', 'build', 'out.json');
const VAR_FOLDERS = abs('var', 'folders', 'x9', 'T', 'pytest-0');
const UNIX_TMP = abs('tmp', 'serve_throwaway.sqlite');

/** Only the FAIL lines, which is what decides the gate. */
const failures = (lines) => lines.filter((line) => line.level === 'FAIL');

describe('ABSOLUTE_PATH_RULES', () => {
  it('names every rule', () => {
    for (const rule of ABSOLUTE_PATH_RULES) {
      expect(typeof rule.name).toBe('string');
      expect(rule.name.length).toBeGreaterThan(0);
      expect(rule.pattern).toBeInstanceOf(RegExp);
    }
  });

  it.each(['paths.mjs', 'paths.test.mjs'])('does not flag %s, which it also scans', (name) => {
    // Both files are tracked, so `run()` reads them. The rules are written with
    // escaped separators, and the samples above are built from fragments,
    // precisely so that the gate can survive scanning its own source.
    const source = readFileSync(new URL(name, import.meta.url), 'utf8');
    expect(failures(scanText(`frontend/scripts/audit/${name}`, source))).toEqual([]);
  });
});

describe('scanText — the paths that fail', () => {
  it.each([
    ['macOS home', `GOOGLE_APPLICATION_CREDENTIALS=${HOME_MAC}`],
    ['Linux home', `rootDir: "${HOME_LINUX}"`],
    ['Windows drive', `configFile: "${DRIVE}"`],
    ['macOS temp', `outputDir: "${PRIVATE_TMP}"`],
    ['macOS sandbox temp', `db at ${VAR_FOLDERS}`],
    ['Unix temp', `db at ${UNIX_TMP}`],
  ])('flags a %s path', (rule, line) => {
    const lines = failures(scanText('docs/example.md', line));
    expect(lines).toHaveLength(1);
    expect(lines[0].text).toContain(`docs/example.md:1 ${rule} path`);
  });

  it('reports the line number and quotes the offending text', () => {
    const [line] = failures(scanText('docs/a.md', `first\nsecond\ncredentials: ${HOME_MAC}`));
    expect(line.text.startsWith('docs/a.md:3 ')).toBe(true);
    expect(line.text).toContain(HOME_MAC);
  });

  it('reports one line per source line even when several roots appear on it', () => {
    expect(failures(scanText('docs/a.md', `${HOME_MAC} ${UNIX_TMP} ${VAR_FOLDERS}`))).toHaveLength(1);
  });

  it('flags every offending line', () => {
    const text = [HOME_MAC, 'fine', HOME_LINUX, 'also fine', UNIX_TMP].join('\n');
    expect(failures(scanText('docs/a.md', text)).map((line) => line.text.split(' ')[0])).toEqual([
      'docs/a.md:1',
      'docs/a.md:3',
      'docs/a.md:5',
    ]);
  });
});

describe('scanText — the paths that pass', () => {
  it.each([
    ['a repo-relative path', 'frontend/e2e/flows/liquidity.spec.ts'],
    ['a URL path', 'http://localhost:5173/liquidity'],
    ['a system binary', abs('usr', 'local', 'bin', 'node')],
    ['a config under etc', abs('etc', 'hosts')],
    ['a bare temp root with no child', abs('tmp')],
    ['a home root with no user', abs('home')],
    // The shapes that made a naive `<letter>:\` rule fail on frozen goldens.
    ['a CSS property before an escape', 'expect(source).toMatch(/-webkit-line-clamp:\\s*2/);'],
    ['a sentence before a newline escape', 'throw new Error(`sub-stages first:\\n- ${missing}`);'],
    ['a log label before a quote escape', 'console.error("save failed:\\", e);'],
    // A one-letter word before a newline escape: the shape that made the
    // archived chromium-motion run's stdout read as a Windows path. Assembled,
    // like the paths above, so this file does not fail on its own sample.
    ['a unit before a newline escape', `"text": "tweens left after 1 s:${BACKSLASH}n   2 / 0  / (landing)"`],
  ])('leaves %s alone', (_what, line) => {
    expect(failures(scanText('src/x.ts', line))).toEqual([]);
  });
});

describe('scanText — the working-directory warning', () => {
  /** Assembled, like the paths above, so this file does not warn on its own samples. */
  const cwd = `process.${'cwd'}()`;
  const source = `const css = readFileSync(resolve(${cwd}, 'src/assets/tokens.css'));`;

  it('warns, and does not fail, under e2e/', () => {
    const lines = scanText('frontend/e2e/checks/chart-tokens.spec.ts', source);
    expect(lines).toHaveLength(1);
    expect(lines[0].level).toBe('WARN');
    expect(lines[0].text).toContain('frontend/e2e/checks/chart-tokens.spec.ts:1');
    expect(lines[0].text).toContain('import.meta.url');
  });

  it('warns under scripts/ too', () => {
    expect(scanText('frontend/scripts/audit/x.mjs', source)[0].level).toBe('WARN');
  });

  it('stays quiet elsewhere', () => {
    expect(scanText('frontend/src/x.ts', source)).toEqual([]);
    expect(scanText('frontend/vite.config.ts', source)).toEqual([]);
  });

  it('does not stop the same line failing on an absolute path', () => {
    const both = scanText('frontend/e2e/x.ts', `readFileSync(resolve(${cwd}, '${HOME_MAC}'))`);
    expect(both.map((line) => line.level)).toEqual(['FAIL', 'WARN']);
  });
});

describe('isSkipped', () => {
  it.each([
    'package-lock.json',
    'frontend/package-lock.json',
    'BackEnd/__pycache__/main.cpython-311.pyc',
    '__pycache__/main.cpython-311.pyc',
    '.claude/settings.json',
    'design-system/logo.png',
    'frontend/public/hero.WEBP',
    'frontend/src/assets/Inter.woff2',
  ])('skips %s', (file) => {
    expect(isSkipped(file)).toBe(true);
  });

  it.each([
    'REPS_README.md',
    'frontend/e2e/reports/phase0-baseline.json',
    'frontend/src/assets/icons.svg',
    'BackEnd/main.py',
    '.gitignore',
    'frontend/scripts/audit/paths.mjs',
  ])('reads %s', (file) => {
    expect(isSkipped(file)).toBe(false);
  });

  it('lists image and font formats as binary', () => {
    for (const extension of ['png', 'jpg', 'webp', 'woff2', 'pdf', 'pyc']) {
      expect(BINARY_EXTENSIONS.has(extension)).toBe(true);
    }
    expect(BINARY_EXTENSIONS.has('svg')).toBe(false);
    expect(BINARY_EXTENSIONS.has('json')).toBe(false);
  });
});

describe('excerpt', () => {
  it('quotes the neighbourhood of the match, elided on both sides', () => {
    const line = `${'x'.repeat(200)}${HOME_MAC}${'y'.repeat(200)}`;
    const text = excerpt(line, 200);
    expect(text.startsWith('…')).toBe(true);
    expect(text.endsWith('…')).toBe(true);
    expect(text.length).toBeLessThan(line.length);
  });

  it('does not elide a short line', () => {
    expect(excerpt('  short line  ', 2)).toBe('short line');
  });
});

describe('run', () => {
  const files = ['a.md', 'package-lock.json'];

  it('passes on a tree with no absolute paths', () => {
    const result = run({ root: '/repo/does-not-exist', files: [] });
    expect(result).toMatchObject({ ok: true, checked: 0, failures: 0, warnings: 0, lines: [] });
  });

  it('skips the files it is told to skip without reading them', () => {
    // Nothing under this root exists, so every read returns null; the lockfile is
    // skipped before the read is even attempted, and both land in `skipped`.
    const result = run({ root: '/repo/does-not-exist', files });
    expect(result.skipped).toBe(2);
    expect(result.checked).toBe(0);
    expect(result.ok).toBe(true);
  });
});

describe('summarize', () => {
  it('counts the files it read when the gate passes', () => {
    expect(summarize({ ok: true, checked: 412, failures: 0, warnings: 0 })).toBe(
      'no absolute filesystem paths in 412 tracked files',
    );
  });

  it('counts the failures, and mentions warnings when there are any', () => {
    expect(summarize({ ok: false, checked: 412, failures: 2, warnings: 4 })).toBe(
      '2 absolute path(s) in tracked files, 4 warning(s)',
    );
  });
});
