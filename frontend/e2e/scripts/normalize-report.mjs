#!/usr/bin/env node
/**
 * `npm run e2e:archive -- <name>` — archive a Playwright JSON report portably.
 *
 * Playwright's JSON reporter records where the run happened: `config.configFile`,
 * `config.rootDir`, every project's `testDir` / `outputDir`, the `argv` it was
 * launched with, and each spec's `file` are all absolute paths on the machine
 * that ran the suite. Committing that verbatim pins the archive to one laptop —
 * the paths are meaningless in CI, on a second checkout, or to a reviewer — and
 * trips gate G8 (`scripts/audit/paths.mjs`), which forbids absolute filesystem
 * paths in tracked files.
 *
 * This script rewrites every string in the report that sits under the repository
 * root to a repo-relative POSIX path (`frontend/e2e/flows/liquidity.spec.ts`) and
 * leaves every other string exactly as it was. It is a pure text substitution on
 * one prefix: no key is renamed, no value is dropped, and the output is
 * re-serialised the way the reporter serialises it (`JSON.stringify(…, null, 2)`,
 * no trailing newline), so a normalised archive differs from the raw report only
 * in the paths.
 *
 * The root is *inferred from the report itself* rather than taken from the local
 * filesystem, so a report produced in CI or on another machine normalises the
 * same way here: `config.configFile` always ends with `CONFIG_FILE_RELATIVE`, and
 * what precedes it is the repository root as that run recorded it. `--root` wins
 * when given, and the CLI falls back to this checkout's root for a report that
 * carries no `configFile`. Re-running on an already-normalised report is a no-op.
 *
 * Paths *outside* the repository root are deliberately untouched: `argv[0]` is
 * the node binary (`/usr/local/bin/node` and the like), which is a fact about the
 * run rather than a reference into this tree, and inventing a relative form for it
 * would falsify the record. Those system paths are not user-specific and are not
 * in G8's pattern set.
 *
 * Usage:
 *   node e2e/scripts/normalize-report.mjs <report.json> [--out <path>] [--root <dir>]
 *   node e2e/scripts/normalize-report.mjs --archive <name>   # last-run.json -> e2e/reports/<name>.json
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/** `frontend/` — three levels up from `e2e/scripts/`. */
export const FRONTEND_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
/** Repository root (parent of `frontend/`). */
export const REPO_ROOT = resolve(FRONTEND_ROOT, '..');

/** Where the JSON reporter writes every run (see `playwright.config.ts`). */
export const LAST_RUN_PATH = join(FRONTEND_ROOT, 'e2e', 'reports', 'last-run.json');
/** Where archived (committed) reports live. */
export const REPORTS_DIR = join(FRONTEND_ROOT, 'e2e', 'reports');

/**
 * The Playwright config's path relative to the repository root. It is the anchor
 * the recorded root is read back from, so it has to match `playwright.config.ts`'s
 * real location; a move breaks inference loudly (root not inferred) rather than
 * silently mis-rewriting.
 */
export const CONFIG_FILE_RELATIVE = 'frontend/playwright.config.ts';

/**
 * A root we are willing to strip: absolute, and not the filesystem root itself.
 * Without this guard a report whose `configFile` was `/frontend/playwright.config.ts`
 * would yield an empty root and rewrite every leading `/` in the file.
 */
const USABLE_ROOT = /^(\/[^/]|[A-Za-z]:\/)/;

/** Backslash-separated paths compared and emitted as POSIX. */
export function toPosix(value) {
  return String(value).replace(/\\/g, '/');
}

/** Escape a literal for use inside a `RegExp`. */
function escapeRegExp(literal) {
  return literal.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * The repository root as `report` recorded it, or `''` when it cannot be read
 * back — an already-normalised report, or one from a differently laid-out tree.
 */
export function inferRepoRoot(report) {
  const configFile = toPosix(report?.config?.configFile ?? '');
  const suffix = `/${CONFIG_FILE_RELATIVE}`;
  if (!configFile.endsWith(suffix)) return '';
  const root = configFile.slice(0, -suffix.length);
  return USABLE_ROOT.test(root) ? root : '';
}

/**
 * `value` with the recorded root removed, or `null` when it did not mention it.
 *
 * Both separator spellings of the root are stripped, and the tail is converted
 * to POSIX so a Windows-recorded report archives to the same relative strings a
 * macOS one does. The root on its own becomes `.` — a report field that names the
 * repository root itself still has to name *something*.
 */
export function stripRoot(value, root) {
  if (typeof value !== 'string' || !root) return null;
  const posixRoot = toPosix(root).replace(/\/+$/, '');
  if (!posixRoot) return null;
  const windowsRoot = posixRoot.replace(/\//g, '\\');
  const separated = new RegExp(
    `(?:${escapeRegExp(posixRoot)}\\/|${escapeRegExp(windowsRoot)}\\\\)([^\\s"']*)`,
    'g',
  );
  let changed = false;
  let next = value.replace(separated, (_match, tail) => {
    changed = true;
    return toPosix(tail);
  });
  if (!changed) {
    if (value !== posixRoot && value !== windowsRoot) return null;
    next = '.';
  }
  return next;
}

/**
 * `report` with every under-the-root path made repo-relative.
 *
 * Returns a new structure; the input is not mutated. `replacements` counts the
 * strings that changed, which is what the CLI reports and what makes a no-op
 * run visible rather than silent.
 */
export function normalizeReport(report, { root = inferRepoRoot(report) } = {}) {
  let replacements = 0;

  const walk = (node) => {
    if (typeof node === 'string') {
      const stripped = stripRoot(node, root);
      if (stripped === null) return node;
      replacements += 1;
      return stripped;
    }
    if (Array.isArray(node)) return node.map(walk);
    if (node && typeof node === 'object') {
      return Object.fromEntries(Object.entries(node).map(([key, value]) => [key, walk(value)]));
    }
    return node;
  };

  return { report: walk(report), replacements, root };
}

/** Serialise the way Playwright's JSON reporter does, so diffs stay path-only. */
export function serializeReport(report) {
  return JSON.stringify(report, null, 2);
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

/** `argv` split into positionals and the `--flag value` pairs we accept. */
export function parseArgs(argv) {
  const options = { positionals: [], out: '', root: '', archive: '' };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--out' || arg === '--root' || arg === '--archive') {
      index += 1;
      options[arg.slice(2)] = argv[index] ?? '';
    } else {
      options.positionals.push(arg);
    }
  }
  return options;
}

const USAGE = [
  'usage: node e2e/scripts/normalize-report.mjs <report.json> [--out <path>] [--root <dir>]',
  '       node e2e/scripts/normalize-report.mjs --archive <name>',
].join('\n');

/** CLI body; returns the exit code so the unit test can drive it. */
export function main(argv, log = console.log) {
  const { positionals, out, root, archive } = parseArgs(argv);
  const name = archive || '';
  if (name && /[/\\]/.test(name)) {
    log(`normalize-report: --archive takes a bare name, not a path: ${name}`);
    return 2;
  }
  const input = name ? LAST_RUN_PATH : positionals[0];
  const output = name ? join(REPORTS_DIR, `${name}.json`) : out || input;
  if (!input) {
    log(USAGE);
    return 2;
  }

  const parsed = JSON.parse(readFileSync(input, 'utf8'));
  // `--root` wins; else the root the report recorded; else this checkout's, which
  // is right for the usual case of archiving a run that just happened here.
  const usedRoot = root || inferRepoRoot(parsed) || REPO_ROOT;
  const result = normalizeReport(parsed, { root: usedRoot });
  writeFileSync(output, serializeReport(result.report), 'utf8');
  log(
    result.replacements > 0
      ? `normalize-report: ${result.replacements} path(s) made relative to ${usedRoot} -> ${output}`
      : `normalize-report: no absolute paths under ${usedRoot} -> ${output}`,
  );
  return 0;
}

if (process.argv[1] !== undefined && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = main(process.argv.slice(2));
}
