#!/usr/bin/env node
/**
 * `npm run audit:contrast` — WCAG 2.x contrast audit of the design tokens.
 *
 * Reads `src/assets/tokens.css`, parses the `--color-*` triplets of both
 * `:root` and `.dark`, and measures every foreground/background pair the UI
 * actually renders. Text pairs must clear 4.5:1 (WCAG AA, normal text); the
 * focus ring is a non-text indicator, so it must clear 3:1.
 *
 * Prints one line per pair per theme and exits 1 if any pair fails. The fix is
 * always to move a token one step within its own colour family — never to
 * lower a threshold.
 *
 * Self-contained on purpose: Node built-ins only, so it runs anywhere.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

/** `src/assets/tokens.css`, resolved relative to this file (never absolute). */
export const TOKENS_URL = new URL('../../src/assets/tokens.css', import.meta.url);

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
];

const NON_TEXT_PAIRS = [
  ['ring', 'page'],
  ['ring', 'surface'],
];

/** Every audited pair, with the threshold it is held to. */
export const CONTRAST_PAIRS = [
  ...TEXT_PAIRS.map(([foreground, background]) => ({ foreground, background, min: TEXT_MIN })),
  ...NON_TEXT_PAIRS.map(([foreground, background]) => ({ foreground, background, min: NON_TEXT_MIN })),
];

export const THEMES = [
  { name: 'light', selector: ':root' },
  { name: 'dark', selector: '.dark' },
];

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

/** The declaration body of the first `<selector> { … }` rule, or ''. */
function ruleBody(css, selector) {
  const start = css.indexOf(selector);
  if (start === -1) return '';
  const open = css.indexOf('{', start);
  const close = css.indexOf('}', open);
  if (open === -1 || close === -1) return '';
  return css.slice(open + 1, close);
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

// ---------------------------------------------------------------------------
// audit
// ---------------------------------------------------------------------------

function formatLine(theme, foreground, background, ratio, min, status) {
  const pair = `${foreground} on ${background}`;
  return `${status} ${theme.padEnd(5)} ${pair.padEnd(34)} ${ratio.toFixed(2)}:1 (min ${min}:1)`;
}

/**
 * Measure every pair in every theme.
 *
 * The dark theme inherits `:root` at runtime, so a token `.dark` does not
 * redefine still resolves to its light value — resolve the same way here.
 */
export function checkThemes(themes) {
  const lines = [];

  for (const { name } of THEMES) {
    const resolved = { ...themes.light, ...(themes[name] ?? {}) };
    for (const { foreground, background, min } of CONTRAST_PAIRS) {
      const fg = resolved[`color-${foreground}`];
      const bg = resolved[`color-${background}`];
      if (!fg || !bg) {
        const missing = [!fg && foreground, !bg && background].filter(Boolean).join(', ');
        lines.push({
          theme: name,
          foreground,
          background,
          ratio: 0,
          min,
          status: 'FAIL',
          text: `FAIL  ${name.padEnd(5)} ${`${foreground} on ${background}`.padEnd(34)} missing token(s): ${missing}`,
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

export function run({ url = TOKENS_URL } = {}) {
  return checkThemes(parseTokens(readFileSync(url, 'utf8')));
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
      ? `CONTRAST PASS ${result.lines.length} pairs, WCAG AA (${TEXT_MIN}:1 text, ${NON_TEXT_MIN}:1 ring)`
      : `CONTRAST FAIL ${failed} of ${result.lines.length} pairs below threshold`,
  );
  if (!result.ok) process.exitCode = 1;
}
