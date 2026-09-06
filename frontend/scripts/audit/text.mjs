/**
 * Gate G4b — copy freeze.
 *
 * Records the on-screen copy of every SFC: the whitespace-collapsed static text
 * nodes and the interpolation expressions of the template, in document order.
 * Re-indenting or re-wrapping markup is invisible; changing a word is not.
 */
import { join } from 'node:path';
import { diffArrays } from 'diff';
import {
  collapse,
  FRONTEND_ROOT,
  GOLDEN_DIR,
  isCliEntry,
  listSfcFiles,
  loadGolden,
  missingGoldenResult,
  parseSfc,
  parseSfcSource,
  readAllowlist,
  reportGate,
  writeJson,
} from './sfc.mjs';

export const GOLDEN_PATH = join(GOLDEN_DIR, 'text.json');

const NODE_TEXT = 2;
const NODE_INTERPOLATION = 5;

/** Ordered on-screen copy of one parsed template. */
export function collectText(descriptor) {
  const copy = [];
  walk(descriptor.template?.ast?.children ?? []);
  return copy;

  function walk(children) {
    for (const node of children) {
      if (node.type === NODE_TEXT) {
        const text = collapse(node.content);
        if (text !== '') copy.push(text);
      } else if (node.type === NODE_INTERPOLATION) {
        copy.push(`{{ ${collapse(node.content?.content ?? '')} }}`);
      } else if (Array.isArray(node.children)) {
        walk(node.children);
      }
    }
  }
}

export function collectTextFromSource(source, file) {
  return collectText(parseSfcSource(source, file).descriptor);
}

export function collectTextFromFile(root, file) {
  return collectText(parseSfc(join(root, file), file).descriptor);
}

export function buildGolden(root = FRONTEND_ROOT) {
  const golden = {};
  for (const file of listSfcFiles(root)) golden[file] = collectTextFromFile(root, file);
  return golden;
}

function isAllowedChange(fileAllowlist, from, to) {
  return fileAllowlist.some((entry) => (entry.from ?? '') === from && (entry.to ?? '') === to);
}

/** Pair adjacent removals with additions so an edit reads as one `from => to`. */
export function diffCopy(file, goldenCopy, currentCopy, fileAllowlist) {
  const parts = diffArrays(goldenCopy, currentCopy);
  const lines = [];

  const report = (from, to) => {
    if (isAllowedChange(fileAllowlist, from, to)) return;
    lines.push({ level: 'FAIL', text: `${file} copy changed: ${JSON.stringify(from)} => ${JSON.stringify(to)}` });
  };

  for (let index = 0; index < parts.length; index += 1) {
    const part = parts[index];
    if (!part.added && !part.removed) continue;
    if (part.removed) {
      const next = parts[index + 1];
      const added = next?.added ? next.value : [];
      if (next?.added) index += 1;
      const pairs = Math.max(part.value.length, added.length);
      for (let i = 0; i < pairs; i += 1) report(part.value[i] ?? '', added[i] ?? '');
      continue;
    }
    for (const value of part.value) report('', value);
  }

  return lines;
}

export function verifyText({ golden, current, allowlist }) {
  const lines = [];
  const fileAllowlists = allowlist.text ?? [];

  for (const file of Object.keys(current).sort()) {
    if (!(file in golden)) lines.push({ level: 'INFO', text: `${file} new file, not frozen` });
  }

  for (const file of Object.keys(golden).sort()) {
    const currentCopy = current[file];
    if (!currentCopy) {
      lines.push({ level: 'FAIL', text: `${file} deleted frozen file` });
      continue;
    }
    lines.push(
      ...diffCopy(file, golden[file], currentCopy, fileAllowlists.filter((e) => e.file === file)),
    );
  }

  return { ok: !lines.some((line) => line.level === 'FAIL'), lines };
}

export function run({ root = FRONTEND_ROOT, write = false } = {}) {
  if (write) {
    const golden = buildGolden(root);
    writeJson(GOLDEN_PATH, golden);
    return {
      ok: true,
      wrote: true,
      lines: [{ level: 'INFO', text: `wrote golden/text.json (${Object.keys(golden).length} files)` }],
    };
  }
  const { golden, missing } = loadGolden(GOLDEN_PATH);
  if (missing) return missingGoldenResult('text.json');
  const current = {};
  for (const file of listSfcFiles(root)) current[file] = collectTextFromFile(root, file);
  return verifyText({ golden, current, allowlist: readAllowlist() });
}

if (isCliEntry(import.meta.url)) {
  reportGate('G4b', run({ write: process.argv.includes('--write') }));
}
