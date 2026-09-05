#!/usr/bin/env node
/**
 * Gate G8 — no absolute filesystem path in a tracked file.
 *
 * An absolute path is a fact about one laptop. Committed, it is at best noise a
 * reviewer has to ignore and at worst a build that only works on the machine
 * that wrote it: a cloud CI runner, a deploy image and a second checkout all
 * have different home directories, and none of them has this one's. The rule is
 * therefore mechanical rather than advisory — every path in a tracked file is
 * repo-relative, and this gate is what keeps it that way.
 *
 * `ABSOLUTE_PATH_RULES` lists what counts: the macOS and Linux home roots, a
 * Windows drive letter, and the three temporary-directory roots a macOS or Linux
 * tool is most likely to bake into generated output. Each is a FAIL. The list is
 * deliberately short: it catches the paths that are actually machine-specific
 * and leaves system paths (a `/usr` binary, a `/etc` config) alone, because
 * those are portable across every machine of the same shape and rewriting them
 * would falsify records that legitimately name them.
 *
 * Every pattern below is written with escaped separators (`\/`) so that this
 * file — which is itself a tracked file the gate scans — does not match its own
 * rules. A test or doc that genuinely needs to talk about such a path builds the
 * string from fragments for the same reason; see `paths.test.mjs`. There is no
 * suppression comment on purpose: an escape hatch would make the repo-wide grep
 * the user runs by hand ("is anything left?") stop answering "no".
 *
 * `CWD_RELATIVE` is the softer sibling and only ever WARNs. A script under
 * `e2e/` or `scripts/` that reads a file through `process.cwd()` is not
 * unportable across machines — it is unportable across *working directories*,
 * so it works under `npm run` from the package root and breaks the moment
 * anything invokes it from elsewhere. The fix is to resolve against
 * `import.meta.url`. It is a warning and not a failure because the offenders
 * left in the tree live in `e2e/fixtures/`, which the behaviour freeze forbids
 * editing; the line keeps them visible until that freeze lifts.
 *
 * Scans tracked files only (`git ls-files`), skipping the lockfile, compiled
 * Python caches, the local agent directory, and anything binary — by extension
 * first, then by a NUL byte in the content, so an unlisted binary format cannot
 * produce a nonsense match.
 *
 * Run on its own with `node scripts/audit/paths.mjs`; runs inside
 * `npm run verify:ui` as gate G8.
 */
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { REPO_ROOT, isCliEntry } from './sfc.mjs';

/** What makes a path machine-specific. Each match is a FAIL. */
export const ABSOLUTE_PATH_RULES = [
  { name: 'macOS home', pattern: /\/Users\// },
  { name: 'Linux home', pattern: /\/home\/[A-Za-z0-9._-]/ },
  // A drive letter needs a word boundary in front of it and *two* path
  // characters behind the separator, or half the escape sequences in the tree —
  // including ones inside frozen goldens — would read as a Windows path.
  // The word boundary alone handles `clamp:\s*2` and `failed:\n`, where a
  // letter precedes the would-be drive letter. It does not handle a one-letter
  // word: the archived Playwright run's stdout says `left after 1 s:` and then
  // a newline, which is `s:` + separator + `n` on disk. A real drive path
  // continues into a segment (`C:` + separator + `work` + …), so requiring a
  // second path character tells the two apart without a file-type special case.
  { name: 'Windows drive', pattern: /(?:^|[^A-Za-z0-9])[A-Za-z]:[\\][\\A-Za-z0-9_.$-]{2,}/ },
  // `\b` rather than a closing separator, so that this line does not itself
  // contain a temp-directory path and fail the rule it declares.
  { name: 'macOS temp', pattern: /\/private\/tmp\b/ },
  { name: 'macOS sandbox temp', pattern: /\/var\/folders/ },
  { name: 'Unix temp', pattern: /\/tmp\// },
];

/**
 * Resolving a file against the process's working directory. WARN only.
 *
 * Matches the read idiom — the working directory handed to `resolve` or `join`
 * — rather than every mention of `process.cwd`, so that a comment or a docblock
 * (this one included) explaining the rule does not trip it.
 */
export const CWD_RELATIVE = /\b(?:resolve|join)\s*\(\s*process\.cwd\(\)/;

/** Where a working-directory-relative read is worth warning about. */
export const CWD_RELATIVE_TREES = /(^|\/)(e2e|scripts)\//;

/** Tracked files the gate never reads. */
export const SKIPPED_PATHS = [
  /(^|\/)package-lock\.json$/,
  /(^|\/)__pycache__\//,
  /^\.claude\//,
];

/** Extensions whose contents are not text and cannot be reviewed line by line. */
export const BINARY_EXTENSIONS = new Set([
  '7z', 'bin', 'bmp', 'bz2', 'class', 'dll', 'dylib', 'eot', 'exe', 'gif', 'gz',
  'heic', 'icns', 'ico', 'jar', 'jpeg', 'jpg', 'mov', 'mp3', 'mp4', 'odt', 'otf',
  'pdf', 'png', 'psd', 'pyc', 'pyd', 'pyo', 'so', 'sqlite', 'sqlite3', 'tar',
  'tgz', 'ttf', 'wasm', 'wav', 'webm', 'webp', 'woff', 'woff2', 'xz', 'zip',
]);

/** How much of an offending line the report quotes. */
const EXCERPT_RADIUS = 40;

/** True when the gate skips `file` outright, without reading it. */
export function isSkipped(file) {
  if (SKIPPED_PATHS.some((pattern) => pattern.test(file))) return true;
  const dot = file.lastIndexOf('.');
  const slash = file.lastIndexOf('/');
  if (dot <= slash + 1) return false;
  return BINARY_EXTENSIONS.has(file.slice(dot + 1).toLowerCase());
}

/** The part of `line` around `index`, trimmed and elided so reports stay one line. */
export function excerpt(line, index) {
  const start = Math.max(0, index - EXCERPT_RADIUS);
  const end = Math.min(line.length, index + EXCERPT_RADIUS);
  return `${start > 0 ? '…' : ''}${line.slice(start, end).trim()}${end < line.length ? '…' : ''}`;
}

/**
 * `{ level, text }` lines for one file's text. At most one absolute-path line per
 * source line: a generated report can put the same root on a thousand lines, and
 * a gate that printed every rule that matched each of them would bury its own
 * verdict.
 */
export function scanText(file, text) {
  const lines = [];
  const warnCwd = CWD_RELATIVE_TREES.test(file);
  const sourceLines = text.split('\n');
  for (let index = 0; index < sourceLines.length; index += 1) {
    const line = sourceLines[index];
    const number = index + 1;
    for (const rule of ABSOLUTE_PATH_RULES) {
      const match = rule.pattern.exec(line);
      if (!match) continue;
      lines.push({
        level: 'FAIL',
        text: `${file}:${number} ${rule.name} path — ${excerpt(line, match.index)}`,
      });
      break;
    }
    if (warnCwd && CWD_RELATIVE.test(line)) {
      lines.push({
        level: 'WARN',
        text: `${file}:${number} reads relative to the working directory; resolve against import.meta.url instead`,
      });
    }
  }
  return lines;
}

/** Every path `git ls-files` reports, repo-relative and `/`-separated. */
export function listTrackedFiles(root = REPO_ROOT) {
  const result = spawnSync('git', ['ls-files', '-z'], {
    cwd: root,
    encoding: 'utf8',
    maxBuffer: 64 * 1024 * 1024,
  });
  if (result.status !== 0) {
    throw new Error(`git ls-files failed in ${root}: ${result.stderr ?? ''}`.trim());
  }
  return (result.stdout ?? '').split('\0').filter(Boolean);
}

/**
 * `file`'s text, or `null` when it is binary or no longer on disk (a tracked
 * file staged for deletion is still listed by `git ls-files`).
 */
export function readTrackedText(absPath) {
  let buffer;
  try {
    buffer = readFileSync(absPath);
  } catch {
    return null;
  }
  return buffer.includes(0) ? null : buffer.toString('utf8');
}

export function run({ root = REPO_ROOT, files = undefined } = {}) {
  const tracked = files ?? listTrackedFiles(root);
  const lines = [];
  let checked = 0;
  let skipped = 0;
  for (const file of tracked) {
    if (isSkipped(file)) {
      skipped += 1;
      continue;
    }
    const text = readTrackedText(join(root, file));
    if (text === null) {
      skipped += 1;
      continue;
    }
    checked += 1;
    lines.push(...scanText(file, text));
  }
  const failures = lines.filter((line) => line.level === 'FAIL').length;
  return { ok: failures === 0, checked, skipped, failures, warnings: lines.length - failures, lines };
}

/** The `verify:ui` detail line, so the gate says the same thing in both places. */
export function summarize(result) {
  const warned = result.warnings > 0 ? `, ${result.warnings} warning(s)` : '';
  return result.ok
    ? `no absolute filesystem paths in ${result.checked} tracked files${warned}`
    : `${result.failures} absolute path(s) in tracked files${warned}`;
}

if (isCliEntry(import.meta.url)) {
  const result = run();
  for (const line of result.lines) console.log(`${line.level} G8 ${line.text}`);
  console.log(`${result.ok ? 'PASS' : 'FAIL'} G8 ${summarize(result)}`);
  if (!result.ok) process.exitCode = 1;
}
