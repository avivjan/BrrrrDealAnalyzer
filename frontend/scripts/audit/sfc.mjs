/**
 * Shared SFC parsing + small path/JSON helpers for the behaviour audit gates.
 *
 * The audit scripts freeze *behaviour*, so they always read the untransformed
 * SFC descriptor: `descriptor.template.ast` is the raw `RootNode` (elements are
 * `type === 1`, static attributes `type === 6`, directives `type === 7`, text
 * `type === 2`, interpolations `type === 5`).
 */
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from '@vue/compiler-sfc';

/** `frontend/` — the npm project root, two levels up from `scripts/audit/`. */
export const FRONTEND_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
/** Repository root (parent of `frontend/`). */
export const REPO_ROOT = resolve(FRONTEND_ROOT, '..');
/** Where the committed golden manifests live. */
export const GOLDEN_DIR = join(FRONTEND_ROOT, 'scripts', 'audit', 'golden');
/** Where accepted, reasoned deviations from the goldens are declared. */
export const ALLOWLIST_PATH = join(FRONTEND_ROOT, 'scripts', 'audit', 'allowlist.json');

/** Sorted, `/`-separated repo-frontend-relative paths of every `src/**\/*.vue`. */
export function listSfcFiles(root = FRONTEND_ROOT) {
  const found = [];
  walk(join(root, 'src'));
  return found.sort();

  function walk(dir) {
    for (const name of readdirSync(dir).sort()) {
      const abs = join(dir, name);
      if (statSync(abs).isDirectory()) walk(abs);
      else if (name.endsWith('.vue')) found.push(relative(root, abs).split(sep).join('/'));
    }
  }
}

/**
 * Parse SFC source text. Any parse error throws: a gate that silently recorded a
 * partial descriptor would report "no drift" for a file it never really read.
 */
export function parseSfcSource(source, filename) {
  const { descriptor, errors } = parse(source, { filename });
  if ((errors ?? []).length > 0) {
    throw new Error(`${filename}: ${errors.map((error) => error.message).join('; ')}`);
  }
  return { file: filename, descriptor };
}

/** Parse an SFC from disk. `file` is the label recorded in the goldens. */
export function parseSfc(absPath, file = absPath) {
  return parseSfcSource(readFileSync(absPath, 'utf8'), file);
}

/** Collapse every whitespace run to a single space and trim. */
export function collapse(text) {
  return String(text ?? '').replace(/\s+/g, ' ').trim();
}

export function readJson(path, fallback = undefined) {
  try {
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch (error) {
    if (error.code === 'ENOENT' && fallback !== undefined) return fallback;
    throw error;
  }
}

export function writeJson(path, value) {
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`);
}

/**
 * Load a golden manifest. A missing file is reported rather than treated as an
 * empty baseline, which would make every gate pass vacuously.
 */
export function loadGolden(path) {
  const golden = readJson(path, false);
  return golden === false ? { golden: {}, missing: true } : { golden, missing: false };
}

/** The result a gate returns when its golden manifest has not been generated yet. */
export function missingGoldenResult(name) {
  return {
    ok: false,
    lines: [{ level: 'FAIL', text: `golden/${name} is missing - run npm run audit:baseline` }],
  };
}

export function readAllowlist(path = ALLOWLIST_PATH) {
  const raw = readJson(path, { scripts: [], bindings: [], text: [] });
  return { scripts: raw.scripts ?? [], bindings: raw.bindings ?? [], text: raw.text ?? [] };
}

/** True when this module URL is the entry point of the current `node` process. */
export function isCliEntry(moduleUrl) {
  return process.argv[1] !== undefined && resolve(process.argv[1]) === fileURLToPath(moduleUrl);
}

/**
 * Print `lines` then the gate verdict, and exit non-zero on failure.
 * Shared by the three gate CLIs so their output shape is identical.
 */
export function reportGate(gate, { ok, lines, wrote = false }) {
  for (const line of lines) console.log(`${line.level} ${line.text}`);
  console.log(`${gate} ${wrote ? 'WROTE' : ok ? 'PASS' : 'FAIL'}`);
  if (!ok) process.exitCode = 1;
}
