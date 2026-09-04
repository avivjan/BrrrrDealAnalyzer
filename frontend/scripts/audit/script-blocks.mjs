/**
 * Gate G3 — script freeze.
 *
 * Every `<script setup>` / `<script>` block of every baseline SFC is frozen.
 * The golden stores the block text itself (not a git ref), so verification
 * never depends on a tag being present.
 *
 * A restyling task may only *add* lines, and only lines that match the narrow
 * allow-list of presentational plumbing below (template refs, `useId`, motion
 * imports). Any removed line fails, except the single E1 exemption for the
 * canvas chart, where a hard-coded colour literal may be swapped for a
 * `chartToken(...)` call in place.
 */
import { createHash } from 'node:crypto';
import { join } from 'node:path';
import { diffLines } from 'diff';
import {
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

export const GOLDEN_PATH = join(GOLDEN_DIR, 'script-blocks.json');

/** Separates the two script blocks inside one golden `content` string. */
export const SCRIPT_SEPARATOR = '\n/*--script--*/\n';

/** The only shapes a restyling task may add to a frozen script block. */
export const ALLOWED_ADDED_LINES = [
  /^import \{[^}]+\} from ["'](\.\.\/)+motion(\/[\w-]+)?["'];?$/,
  /^import \{\s*(ref|useId)(\s*,\s*(ref|useId))?\s*\} from ["']vue["'];?$/,
  /^const \w+Ref = ref<HTMLElement \| null>\(null\);?$/,
  /^const \w+Id = useId\(\);?$/,
];

/** E1: the one file allowed to replace colour literals with chart tokens. */
export const E1_FILE = 'src/components/liquidity/TimelineChart.vue';
const E1_IMPORT = /^import \{ chartToken \} from ["']\.\.\/\.\.\/design\/chartTokens["'];?$/;

/** The frozen text of both script blocks of one SFC. */
export function scriptContent(descriptor) {
  const setup = descriptor.scriptSetup?.content ?? '';
  const plain = descriptor.script?.content ?? '';
  return `${setup}${SCRIPT_SEPARATOR}${plain}`;
}

export function sha256(text) {
  return createHash('sha256').update(text, 'utf8').digest('hex');
}

export function goldenEntry(content) {
  return { sha256: sha256(content), lines: content.split('\n').length, content };
}

/** Golden entry for inline SFC source — the shape the unit tests build fixtures with. */
export function entryFromSource(source, file) {
  return goldenEntry(scriptContent(parseSfcSource(source, file).descriptor));
}

/** Golden entry for an SFC on disk. */
export function entryFromFile(root, file) {
  return goldenEntry(scriptContent(parseSfc(join(root, file), file).descriptor));
}

export function buildGolden(root = FRONTEND_ROOT) {
  const golden = {};
  for (const file of listSfcFiles(root)) golden[file] = entryFromFile(root, file);
  return golden;
}

/** Split a golden `content` string back into its two named blocks. */
export function splitBlocks(content) {
  const at = content.indexOf(SCRIPT_SEPARATOR);
  if (at === -1) return [{ name: 'script-setup', text: content }];
  return [
    { name: 'script-setup', text: content.slice(0, at) },
    { name: 'script', text: content.slice(at + SCRIPT_SEPARATOR.length) },
  ];
}

function stripTrailingWhitespace(text) {
  return text
    .split('\n')
    .map((line) => line.replace(/[ \t]+$/, ''))
    .join('\n');
}

function partLines(part) {
  const lines = part.value.split('\n');
  if (lines.length > 0 && lines[lines.length - 1] === '') lines.pop();
  return lines;
}

/**
 * True when every line before `upto` belongs to the leading import block
 * (imports, blank lines and comments only). Multi-line imports are tracked so a
 * `{`-per-line import list does not end the block early.
 */
export function isInImportBlock(lines, upto) {
  let continuingImport = false;
  for (let index = 0; index < upto; index += 1) {
    const line = (lines[index] ?? '').trim();
    if (continuingImport) {
      if (/\bfrom\b|;$/.test(line)) continuingImport = false;
      continue;
    }
    if (line === '') continue;
    if (line.startsWith('//') || line.startsWith('/*') || line.startsWith('*')) continue;
    if (/^import\b/.test(line)) {
      if (!/\bfrom\b/.test(line) && !line.endsWith(';')) continuingImport = true;
      continue;
    }
    return false;
  }
  return true;
}

/**
 * E1 pairing test: the added line must be the removed line with each colour
 * literal replaced by a `chartToken('<name>')` call, and nothing else.
 */
export function isChartTokenSubstitution(added, removed) {
  return (
    added.trim().replace(/chartToken\('[\w-]+'\)/g, '§') ===
    removed.trim().replace(/'(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))'/g, '§')
  );
}

function isAllowedAddedLine(line, isE1) {
  const trimmed = line.trim();
  if (ALLOWED_ADDED_LINES.some((pattern) => pattern.test(trimmed))) return true;
  return isE1 && E1_IMPORT.test(trimmed);
}

/** Diff one script block and apply rules 1-4. Returns problem records. */
function compareBlock({ file, blockName, goldenText, currentText, isE1 }) {
  const problems = [];
  const goldenNormalised = stripTrailingWhitespace(goldenText);
  const currentNormalised = stripTrailingWhitespace(currentText);
  if (goldenNormalised === currentNormalised) return problems;

  const parts = diffLines(goldenNormalised, currentNormalised);
  const currentLines = currentNormalised.split('\n');

  // Materialise every part with its line numbers in the golden / current block.
  let goldenLine = 1;
  let currentLine = 1;
  const records = parts.map((part) => {
    const lines = partLines(part);
    const record = {
      added: Boolean(part.added),
      removed: Boolean(part.removed),
      lines,
      goldenStart: goldenLine,
      currentStart: currentLine,
    };
    if (!part.added) goldenLine += lines.length;
    if (!part.removed) currentLine += lines.length;
    return record;
  });

  // E1: a removed line is forgiven when the added line at the same position of
  // the adjacent hunk is the same line with colour literals tokenised.
  const substituted = new Set();
  if (isE1) {
    for (let index = 0; index < records.length - 1; index += 1) {
      const removedPart = records[index];
      const addedPart = records[index + 1];
      if (!removedPart.removed || !addedPart.added) continue;
      const pairs = Math.min(removedPart.lines.length, addedPart.lines.length);
      for (let offset = 0; offset < pairs; offset += 1) {
        if (isChartTokenSubstitution(addedPart.lines[offset], removedPart.lines[offset])) {
          substituted.add(`${index}:${offset}`);
          substituted.add(`${index + 1}:${offset}`);
        }
      }
    }
  }

  records.forEach((record, index) => {
    if (record.removed) {
      record.lines.forEach((line, offset) => {
        if (substituted.has(`${index}:${offset}`)) return;
        problems.push({
          level: 'FAIL',
          text: `${file} [${blockName} L${record.goldenStart + offset}] removed line: ${line.trim()}`,
        });
      });
      return;
    }
    if (!record.added) return;
    const trailing = records.slice(index + 1).every((later) => later.added);
    record.lines.forEach((line, offset) => {
      if (substituted.has(`${index}:${offset}`)) return;
      const at = record.currentStart + offset;
      if (!isAllowedAddedLine(line, isE1)) {
        problems.push({
          level: 'FAIL',
          text: `${file} [${blockName} L${at}] added line not allowed: ${line.trim()}`,
        });
        return;
      }
      if (!trailing && !isInImportBlock(currentLines, at - 1)) {
        problems.push({
          level: 'FAIL',
          text:
            `${file} [${blockName} L${at}] misplaced added line ` +
            `(must be in the import block or after the last baseline line): ${line.trim()}`,
        });
      }
    });
  });

  return problems;
}

/** Compare the frozen script text of one file. */
export function compareScriptBlocks({ file, goldenContent, currentContent }) {
  const changed =
    stripTrailingWhitespace(goldenContent) !== stripTrailingWhitespace(currentContent);
  if (!changed) return { changed: false, problems: [] };

  const isE1 = file === E1_FILE;
  const goldenBlocks = splitBlocks(goldenContent);
  const currentBlocks = splitBlocks(currentContent);
  const problems = [];
  for (let index = 0; index < Math.max(goldenBlocks.length, currentBlocks.length); index += 1) {
    const blockName = (goldenBlocks[index] ?? currentBlocks[index]).name;
    problems.push(
      ...compareBlock({
        file,
        blockName,
        goldenText: goldenBlocks[index]?.text ?? '',
        currentText: currentBlocks[index]?.text ?? '',
        isE1,
      }),
    );
  }
  return { changed: true, problems };
}

/** Verify a whole golden map against the current tree's entries. */
export function verifyScriptBlocks({ golden, current, allowlist }) {
  const lines = [];
  const allowlisted = new Set((allowlist.scripts ?? []).map((entry) => entry.file));
  const changedFiles = new Set();

  for (const file of Object.keys(current).sort()) {
    if (!(file in golden)) {
      lines.push({ level: 'INFO', text: `${file} new file, not frozen` });
    }
  }

  for (const file of Object.keys(golden).sort()) {
    const currentEntry = current[file];
    if (!currentEntry) {
      lines.push({ level: 'FAIL', text: `${file} deleted frozen file` });
      continue;
    }
    if (currentEntry.sha256 === golden[file].sha256) continue;

    const { changed, problems } = compareScriptBlocks({
      file,
      goldenContent: golden[file].content,
      currentContent: currentEntry.content,
    });
    lines.push(...problems);
    if (changed) changedFiles.add(file);
    if (!changed || problems.length > 0) continue;

    if (!allowlisted.has(file)) {
      lines.push({
        level: 'FAIL',
        text: `${file} unlisted script change (add an allowlist.json "scripts" entry with a reason)`,
      });
    }
  }

  for (const entry of allowlist.scripts ?? []) {
    if (!changedFiles.has(entry.file)) {
      lines.push({
        level: 'WARN',
        text: `${entry.file} allowlist "scripts" entry without a diff (${entry.reason ?? 'no reason'})`,
      });
    }
  }

  return { ok: !lines.some((line) => line.level === 'FAIL'), lines };
}

/** CLI body: `--write` regenerates the golden, otherwise verify the working tree. */
export function run({ root = FRONTEND_ROOT, write = false } = {}) {
  if (write) {
    const golden = buildGolden(root);
    writeJson(GOLDEN_PATH, golden);
    return {
      ok: true,
      wrote: true,
      lines: [
        { level: 'INFO', text: `wrote golden/script-blocks.json (${Object.keys(golden).length} files)` },
      ],
    };
  }
  const { golden, missing } = loadGolden(GOLDEN_PATH);
  if (missing) return missingGoldenResult('script-blocks.json');
  const current = {};
  for (const file of listSfcFiles(root)) current[file] = entryFromFile(root, file);
  return verifyScriptBlocks({ golden, current, allowlist: readAllowlist() });
}

if (isCliEntry(import.meta.url)) {
  reportGate('G3', run({ write: process.argv.includes('--write') }));
}
