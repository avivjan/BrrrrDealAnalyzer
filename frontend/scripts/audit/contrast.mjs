#!/usr/bin/env node
/**
 * `npm run audit:contrast` — WCAG 2.x contrast audit of the design tokens.
 *
 * Reads `src/assets/tokens.css` (the base `:root` / `.dark` set) and every
 * look sheet in `src/assets/looks/*.css` (`[data-look="<id>"]` light and
 * `[data-look="<id>"].dark`), and measures every foreground/background pair
 * the UI actually renders in each set. Text pairs must clear 4.5:1 (WCAG AA,
 * normal text); the focus ring and the primary accent used as a boundary are
 * non-text indicators, so they must clear 3:1.
 *
 * Prints one line per pair per theme and exits 1 if any pair fails. The fix is
 * always to move a token one step within its own colour family — never to
 * lower a threshold.
 *
 * Self-contained on purpose: Node built-ins only, so it runs anywhere.
 */
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

/** `src/assets/tokens.css`, resolved relative to this file (never absolute). */
export const TOKENS_URL = new URL('../../src/assets/tokens.css', import.meta.url);
/** The generated look sheets. Absent until Task 1.1b lands; the base set is audited alone then. */
export const LOOKS_DIR_URL = new URL('../../src/assets/looks/', import.meta.url);

/** WCAG AA: 4.5:1 for normal text, 3:1 for a non-text indicator. */
export const TEXT_MIN = 4.5;
export const NON_TEXT_MIN = 3;

const TEXT_PAIRS = [
  ['fg', 'page'],
  ['fg', 'surface'],
  ['fg', 'surface-muted'],
  ['fg-muted', 'page'],
  ['fg-muted', 'surface'],
  ['fg-muted', 'surface-muted'],
  ['primary-fg', 'primary'],
  ['primary-fg', 'primary-hover'],
  ['positive', 'surface'],
  ['negative', 'surface'],
  ['warning', 'surface'],
  ['positive', 'page'],
  ['negative', 'page'],
  ['warning', 'page'],
  // v2: the elevation tiers carry body text and semantic figures too, and the
  // accent is used as text (eyebrow labels, active nav labels).
  ['fg', 'surface-2'],
  ['fg', 'surface-3'],
  ['fg-muted', 'surface-2'],
  ['fg-muted', 'surface-3'],
  ['positive', 'surface-2'],
  ['negative', 'surface-2'],
  ['warning', 'surface-2'],
  ['accent', 'surface'],
  ['accent', 'page'],
];

const NON_TEXT_PAIRS = [
  ['ring', 'page'],
  ['ring', 'surface'],
  ['ring', 'surface-2'],
  // The primary colour as a boundary or icon on the base surface.
  ['primary', 'surface'],
];

/**
 * Text on a translucent *wash* of a tone over the base surface — the badge,
 * chip and banner pattern (`bg-warning/10 text-warning`, `bg-warning/20` with
 * muted ink). The wash is composited here exactly as the browser does it,
 * `alpha × tone + (1 − alpha) × surface`, so the audit sees the colour the
 * reader sees. `[foreground, tone, alpha]`, always over `surface`.
 */
const WASH_PAIRS = [
  ['primary', 'primary', 0.1],
  ['accent', 'accent', 0.1],
  ['positive', 'positive', 0.1],
  ['negative', 'negative', 0.1],
  ['warning', 'warning', 0.1],
  // Muted ink on a `warning/20` label that itself sits inside a `warning/10`
  // banner over the page (the REPS config notice): the washes compound to
  // ≈33% of the tone — the value axe measured on that element.
  ['fg-muted', 'warning', 0.33],
  ['fg', 'primary', 0.12],
];

/** Every audited pair, with the threshold it is held to. */
export const CONTRAST_PAIRS = [
  ...TEXT_PAIRS.map(([foreground, background]) => ({ foreground, background, min: TEXT_MIN })),
  ...NON_TEXT_PAIRS.map(([foreground, background]) => ({ foreground, background, min: NON_TEXT_MIN })),
  ...WASH_PAIRS.map(([foreground, tone, alpha]) => ({
    foreground,
    background: `${tone}/${Math.round(alpha * 100)} on surface`,
    wash: { tone, alpha },
    min: TEXT_MIN,
  })),
];

/** `alpha × over + (1 − alpha) × under`, per channel, rounded like a rasteriser. */
export function composite(over, under, alpha) {
  return over.map((channel, i) => Math.round(alpha * channel + (1 - alpha) * under[i]));
}

/** The base set in `tokens.css`. */
export const THEMES = [
  { name: 'light', selector: ':root' },
  { name: 'dark', selector: '.dark' },
];

/**
 * The two rule blocks of one look sheet. The generator writes each block's
 * canonical selector first in its selector list, and `ruleBody` requires the
 * selector at the start of a rule, so `.dark [data-look="x"]` later in the
 * dark list can never be mistaken for the light block.
 */
export function lookThemes(id) {
  return [
    { name: `${id}-light`, selector: `[data-look="${id}"]` },
    { name: `${id}-dark`, selector: `[data-look="${id}"].dark` },
  ];
}

// ---------------------------------------------------------------------------
// maths
// ---------------------------------------------------------------------------

/** WCAG relative luminance of an sRGB triplet, each channel 0–255. */
export function relativeLuminance([red, green, blue]) {
  const linear = (channel) => {
    const c = channel / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue);
}

/** WCAG contrast ratio between two sRGB triplets (order-independent, 1–21). */
export function contrastRatio(a, b) {
  const first = relativeLuminance(a);
  const second = relativeLuminance(b);
  const lighter = Math.max(first, second);
  const darker = Math.min(first, second);
  return (lighter + 0.05) / (darker + 0.05);
}

// ---------------------------------------------------------------------------
// parsing
// ---------------------------------------------------------------------------

function stripComments(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, '');
}

/**
 * The declaration body of the first rule whose selector list *starts with*
 * `selector`, or ''.
 *
 * The selector has to match at a boundary — `.darker` and `.theme.dark` are
 * different rules and must not be mistaken for `.dark` — and may be followed
 * by more selectors in the same list (`[data-look="x"], .foo {`). The end of
 * the block is found by counting brace depth, so a nested at-rule
 * (`@supports`, `@media`) inside the theme does not cut the body short.
 * Comments are stripped before this runs, so no brace here comes from one.
 */
export function ruleBody(rawCss, selector) {
  // Idempotent: callers may or may not have stripped comments already, and a
  // header comment before the first rule must not hide that rule.
  const css = stripComments(rawCss);
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const opener = new RegExp(`(?:^|[};])\\s*${escaped}\\s*(?:,[^{]*)?\\{`);
  const match = opener.exec(css);
  if (!match) return '';

  const open = match.index + match[0].length - 1;
  let depth = 0;
  for (let index = open; index < css.length; index += 1) {
    const character = css[index];
    if (character === '{') depth += 1;
    else if (character === '}') {
      depth -= 1;
      if (depth === 0) return css.slice(open + 1, index);
    }
  }
  return ''; // unbalanced braces: report nothing rather than half a rule
}

/**
 * `--color-*` triplets of one rule body, as `{ 'color-fg': [15, 23, 42] }`.
 * Tokens that are not colours (radii, durations) and colours that are resolved
 * strings rather than triplets (the `--chart-*` canvas literals) are skipped:
 * only a triplet can be contrast-checked.
 */
export function parseTriplets(body) {
  const tokens = {};
  for (const [, name, value] of body.matchAll(/--([\w-]+)\s*:\s*([^;]+);/g)) {
    if (!name.startsWith('color-')) continue;
    const triplet = value.trim().match(/^(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})$/);
    if (!triplet) continue;
    tokens[name] = [Number(triplet[1]), Number(triplet[2]), Number(triplet[3])];
  }
  return tokens;
}

/** `{ light, dark }` colour tokens of a `tokens.css` source. */
export function parseTokens(css) {
  const bare = stripComments(css);
  const themes = {};
  for (const { name, selector } of THEMES) themes[name] = parseTriplets(ruleBody(bare, selector));
  return themes;
}

/** `{ '<id>-light', '<id>-dark' }` colour tokens of one look sheet. */
export function parseLook(css, id) {
  const bare = stripComments(css);
  const themes = {};
  for (const { name, selector } of lookThemes(id)) themes[name] = parseTriplets(ruleBody(bare, selector));
  return themes;
}

/** Every `<id>.css` under the looks dir, as `[id, css]`, or none when the dir is absent. */
export function readLookSheets(dirUrl = LOOKS_DIR_URL) {
  const dir = fileURLToPath(dirUrl);
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((file) => file.endsWith('.css'))
    .sort()
    .map((file) => [file.replace(/\.css$/, ''), readFileSync(new URL(file, dirUrl), 'utf8')]);
}

// ---------------------------------------------------------------------------
// audit
// ---------------------------------------------------------------------------

function formatLine(theme, foreground, background, ratio, min, status) {
  const pair = `${foreground} on ${background}`;
  return `${status} ${theme.padEnd(14)} ${pair.padEnd(36)} ${ratio.toFixed(2)}:1 (min ${min}:1)`;
}

/**
 * Measure every pair in every theme.
 *
 * `themes.light` is the base every other set inherits from at runtime (a look
 * sheet, or `.dark`, only overrides what it declares), so each set is
 * resolved over it before measuring. `names` defaults to the base pair, and
 * callers pass the look sets to audit those on top.
 */
export function checkThemes(themes, names = THEMES.map((theme) => theme.name)) {
  const lines = [];

  for (const name of names) {
    const resolved = { ...themes.light, ...(themes[name] ?? {}) };
    for (const { foreground, background, min, wash } of CONTRAST_PAIRS) {
      const fg = resolved[`color-${foreground}`];
      const bg = wash
        ? resolved[`color-${wash.tone}`] && resolved['color-surface']
          ? composite(resolved[`color-${wash.tone}`], resolved['color-surface'], wash.alpha)
          : undefined
        : resolved[`color-${background}`];
      if (!fg || !bg) {
        const missing = [!fg && foreground, !bg && (wash ? `${wash.tone}, surface` : background)].filter(Boolean).join(', ');
        lines.push({
          theme: name,
          foreground,
          background,
          ratio: 0,
          min,
          status: 'FAIL',
          text: `FAIL  ${name.padEnd(14)} ${`${foreground} on ${background}`.padEnd(36)} missing token(s): ${missing}`,
        });
        continue;
      }
      const ratio = contrastRatio(fg, bg);
      const status = ratio >= min ? 'PASS' : 'FAIL';
      lines.push({
        theme: name,
        foreground,
        background,
        ratio,
        min,
        status,
        text: formatLine(name, foreground, background, ratio, min, status),
      });
    }
  }

  return { ok: !lines.some((line) => line.status === 'FAIL'), lines };
}

/**
 * The base set plus every look sheet, one result. A look's light block is
 * resolved over the base light set (what the browser does when a look omits a
 * token) and its dark block over the same base — the generator writes every
 * token into both blocks, and `looks.test.ts` proves it, so in practice each
 * look set stands on its own.
 */
export function run({ url = TOKENS_URL, looksDir = LOOKS_DIR_URL } = {}) {
  const base = parseTokens(readFileSync(url, 'utf8'));
  const themes = { ...base };
  const names = THEMES.map((theme) => theme.name);
  for (const [id, css] of readLookSheets(looksDir)) {
    Object.assign(themes, parseLook(css, id));
    names.push(...lookThemes(id).map((theme) => theme.name));
  }
  return checkThemes(themes, names);
}

function isCliEntry(moduleUrl) {
  const entry = process.argv[1];
  return Boolean(entry) && fileURLToPath(moduleUrl) === entry;
}

if (isCliEntry(import.meta.url)) {
  const result = run();
  for (const line of result.lines) console.log(line.text);
  const failed = result.lines.filter((line) => line.status === 'FAIL').length;
  console.log('');
  console.log(
    result.ok
      ? `CONTRAST PASS ${result.lines.length} pairs across ${new Set(result.lines.map((line) => line.theme)).size} sets, WCAG AA (${TEXT_MIN}:1 text, ${NON_TEXT_MIN}:1 non-text)`
      : `CONTRAST FAIL ${failed} of ${result.lines.length} pairs below threshold`,
  );
  if (!result.ok) process.exitCode = 1;
}
