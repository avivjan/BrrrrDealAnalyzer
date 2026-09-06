#!/usr/bin/env node
/**
 * `node scripts/design/build-looks.mjs` — write `src/assets/looks/<id>.css`
 * for every look in `looks.data.mjs`. `--check` writes nothing and exits 1 if
 * any committed sheet differs from what the data produces (the guard
 * `src/design/looks.test.ts` runs in `npm test`).
 *
 * A sheet is two rules. The light rule's selector list starts with
 * `[data-look="<id>"]`, the dark rule's with `[data-look="<id>"].dark`; the
 * contrast audit relies on that order. The extra members let a
 * `LookPreview` card render any look in either mode inside a page that is
 * showing another:
 *
 *   light:  [data-look=x], [data-look=x][data-mode=light], .dark [data-look=x][data-mode=light]
 *   dark:   [data-look=x].dark, .dark [data-look=x], [data-look=x][data-mode=dark]
 *
 * Every token in `TOKEN_NAMES` is written into both rules, so a look never
 * inherits a value from the base `tokens.css` by accident (a dark look
 * inheriting the base's *light* surface is exactly the bug that would cause).
 */
import { mkdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { LOOKS } from './looks.data.mjs';

export const LOOKS_DIR_URL = new URL('../../src/assets/looks/', import.meta.url);

// ---------------------------------------------------------------------------
// colour helpers
// ---------------------------------------------------------------------------

export function hexToRgb(hex) {
  const clean = hex.replace('#', '');
  const full = clean.length === 3 ? clean.split('').map((c) => c + c).join('') : clean;
  const n = Number.parseInt(full, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

const triplet = (hex) => hexToRgb(hex).join(' ');
const rgba = (hex, alpha) => `rgba(${hexToRgb(hex).join(', ')}, ${alpha})`;
const rgb = (hex) => `rgb(${hexToRgb(hex).join(' ')})`;

/** `a` moved `t` of the way toward `b`, as a hex string. */
export function mix(a, b, t) {
  const from = hexToRgb(a);
  const to = hexToRgb(b);
  const channel = (i) => Math.round(from[i] + (to[i] - from[i]) * t).toString(16).padStart(2, '0');
  return `#${channel(0)}${channel(1)}${channel(2)}`;
}

// ---------------------------------------------------------------------------
// the vocabulary
// ---------------------------------------------------------------------------

/** `--color-*` triplets, in the order they are written. */
export const COLOR_TOKENS = [
  ['page', 'page'], ['surface', 'surface'], ['surface-muted', 'surfaceMuted'], ['surface-2', 'surface2'],
  ['surface-3', 'surface3'], ['line', 'line'], ['fg', 'fg'], ['fg-muted', 'fgMuted'],
  ['primary', 'primary'], ['primary-hover', 'primaryHover'], ['primary-fg', 'primaryFg'],
  ['accent', 'accent'], ['accent-2', 'accent2'],
  ['positive', 'positive'], ['negative', 'negative'], ['warning', 'warning'], ['ring', 'ring'],
  ['glass', 'glass'], ['glass-line', 'glassLine'],
];

export const CHART_NAMES = [
  'bg', 'grid', 'axis-text', 'reserve-band', 'weekend-band', 'today-band', 'month-line', 'day-line',
  'month-label', 'day-today', 'day-hover', 'day-active', 'day-idle', 'marker-today', 'marker-idle',
  'today-line', 'net-positive', 'net-negative', 'inflow-fill-hover', 'inflow-fill', 'inflow-stroke-hover',
  'inflow-stroke', 'outflow-fill-hover', 'outflow-fill', 'outflow-stroke-hover', 'outflow-stroke',
  'reserve-line', 'baseline', 'balance-dot', 'balance-dot-core', 'min-negative', 'min-warning',
];

/** Every custom property a look sheet must declare, in both of its rules. */
export const TOKEN_NAMES = [
  ...COLOR_TOKENS.map(([name]) => `--color-${name}`),
  ...Array.from({ length: 8 }, (_, i) => `--color-chart-${i + 1}`),
  ...CHART_NAMES.map((name) => `--chart-${name}`),
  '--radius-sm', '--radius-md', '--radius-lg', '--border-w',
  '--shadow-1', '--shadow-2', '--shadow-3', '--shadow-4',
  '--glow-primary', '--glow-accent', '--glow-negative', '--blur-glass',
  '--gradient-brand', '--gradient-surface',
  '--font-display', '--font-mono', '--track-display',
  '--dur-fast', '--dur-base', '--dur-slow',
  '--ease-standard', '--ease-emphasized', '--ease-exit',
  '--gsap-ease-standard', '--gsap-ease-emphasized', '--gsap-ease-exit',
  '--ambient', '--ambient-play', '--ambient-opacity',
];

// ---------------------------------------------------------------------------
// derivations
// ---------------------------------------------------------------------------

/**
 * The 32 chart literals for one palette — the mapping v1 Task 3.9 wrote by
 * hand for the light theme, applied to any palette. Scaffolding (grid, day
 * rules, wash bands) sits below 3:1 on purpose; ink and semantic lines are
 * palette colours that the contrast audit already holds to 4.5:1 on surface.
 */
export function chartLiterals(p, mode) {
  const washFg = mode === 'dark' ? 0.04 : 0.03;
  return {
    bg: p.surface,
    grid: p.line,
    'axis-text': p.fgMuted,
    'reserve-band': rgba(p.negative, 0.06),
    'weekend-band': rgba(p.fg, washFg),
    'today-band': rgba(p.primary, 0.08),
    'month-line': mix(p.line, p.fg, 0.18),
    'day-line': p.line,
    'month-label': p.fgMuted,
    'day-today': p.primary,
    'day-hover': p.primaryHover,
    'day-active': p.fg,
    'day-idle': rgba(p.fgMuted, 0.7),
    'marker-today': p.primary,
    'marker-idle': rgba(p.fgMuted, 0.65),
    'today-line': p.primary,
    'net-positive': p.positive,
    'net-negative': p.negative,
    'inflow-fill-hover': rgba(p.primary, 0.55),
    'inflow-fill': rgba(p.primary, 0.35),
    'inflow-stroke-hover': p.primaryHover,
    'inflow-stroke': p.primary,
    'outflow-fill-hover': rgba(p.negative, 0.55),
    'outflow-fill': rgba(p.negative, 0.35),
    'outflow-stroke-hover': mix(p.negative, p.fg, 0.2),
    'outflow-stroke': p.negative,
    'reserve-line': p.negative,
    baseline: rgba(p.fgMuted, 0.2),
    'balance-dot': p.primary,
    'balance-dot-core': p.surface,
    'min-negative': p.negative,
    'min-warning': p.warning,
  };
}

function shadows(style, p, mode) {
  const ink = mode === 'dark' ? '#000000' : p.fg;
  const a = mode === 'dark' ? [0.35, 0.4, 0.5, 0.6] : [0.06, 0.08, 0.12, 0.18];
  switch (style) {
    case 'flat':
      // A hairline ring instead of a drop: depth is drawn, not lit.
      return [
        `0 0 0 1px ${rgba(p.line, 0.9)}`,
        `0 0 0 1px ${rgba(p.line, 1)}`,
        `0 0 0 1px ${rgba(p.line, 1)}, 0 8px 24px -12px ${rgba(ink, a[2])}`,
        `0 0 0 1px ${rgba(p.line, 1)}, 0 24px 48px -16px ${rgba(ink, a[3])}`,
      ];
    case 'hard':
      // Offset blocks in the line colour: brutalism's one depth cue.
      return [
        `3px 3px 0 ${rgb(p.line)}`,
        `6px 6px 0 ${rgb(p.line)}`,
        `8px 8px 0 ${rgb(p.line)}`,
        `12px 12px 0 ${rgb(p.line)}`,
      ];
    case 'soft-deep':
      return [
        `0 1px 2px 0 ${rgba(ink, a[0])}`,
        `0 8px 24px -8px ${rgba(ink, a[1] * 1.5)}, 0 2px 6px -2px ${rgba(ink, a[0])}`,
        `0 20px 40px -12px ${rgba(ink, a[2] * 1.5)}, 0 6px 12px -6px ${rgba(ink, a[1])}`,
        `0 32px 64px -16px ${rgba(ink, a[3] * 1.4)}, 0 12px 24px -12px ${rgba(ink, a[2])}`,
      ];
    default: // soft
      return [
        `0 1px 2px 0 ${rgba(ink, a[0])}`,
        `0 4px 6px -1px ${rgba(ink, a[1])}, 0 2px 4px -2px ${rgba(ink, a[0])}`,
        `0 12px 20px -6px ${rgba(ink, a[2])}, 0 4px 8px -4px ${rgba(ink, a[1])}`,
        `0 24px 48px -12px ${rgba(ink, a[3])}, 0 8px 16px -8px ${rgba(ink, a[2])}`,
      ];
  }
}

/** The declarations of one look in one mode, as `[name, value]` in TOKEN_NAMES order. */
export function declarations(look, mode) {
  const p = look[mode];
  const s = look.shape;
  const map = new Map();
  for (const [name, key] of COLOR_TOKENS) map.set(`--color-${name}`, triplet(p[key]));
  p.chart.forEach((hex, i) => map.set(`--color-chart-${i + 1}`, triplet(hex)));
  for (const [name, value] of Object.entries(chartLiterals(p, mode))) map.set(`--chart-${name}`, value);
  map.set('--radius-sm', s.radius[0]);
  map.set('--radius-md', s.radius[1]);
  map.set('--radius-lg', s.radius[2]);
  map.set('--border-w', s.borderW);
  shadows(s.shadows, p, mode).forEach((value, i) => map.set(`--shadow-${i + 1}`, value));
  const none = '0 0 0 0 transparent';
  map.set('--glow-primary', s.glow ? `0 0 24px ${rgba(p.primary, mode === 'dark' ? 0.45 : 0.3)}` : none);
  map.set('--glow-accent', s.glow ? `0 0 20px ${rgba(p.accent2, mode === 'dark' ? 0.4 : 0.25)}` : none);
  map.set('--glow-negative', s.glow ? `0 0 20px ${rgba(p.negative, 0.35)}` : none);
  map.set('--blur-glass', s.blur);
  map.set('--gradient-brand', `linear-gradient(135deg, ${rgb(p.primary)}, ${rgb(p.accent2)})`);
  map.set('--gradient-surface', `linear-gradient(180deg, ${rgb(p.surface)}, ${rgb(p.page)})`);
  map.set('--font-display', s.fontDisplay);
  map.set('--font-mono', s.fontMono);
  map.set('--track-display', s.trackDisplay);
  map.set('--dur-fast', s.dur[0]);
  map.set('--dur-base', s.dur[1]);
  map.set('--dur-slow', s.dur[2]);
  map.set('--ease-standard', s.ease.standard);
  map.set('--ease-emphasized', s.ease.emphasized);
  map.set('--ease-exit', s.ease.exit);
  map.set('--gsap-ease-standard', s.gsap.standard);
  map.set('--gsap-ease-emphasized', s.gsap.emphasized);
  map.set('--gsap-ease-exit', s.gsap.exit);
  map.set('--ambient', s.ambient);
  // Consumable forms of `--ambient`: whether the dashboard's background moves, and how visible it is.
  map.set('--ambient-play', s.ambient === 'none' ? 'paused' : 'running');
  map.set('--ambient-opacity', s.ambient === 'none' ? '0.12' : '0.35');
  return TOKEN_NAMES.map((name) => {
    if (!map.has(name)) throw new Error(`${look.id}/${mode}: no value for ${name}`);
    return [name, map.get(name)];
  });
}

export function renderLook(look) {
  const id = look.id;
  const block = (selectors, mode) =>
    `${selectors.join(',\n')} {\n${declarations(look, mode)
      .map(([name, value]) => `  ${name}: ${value};`)
      .join('\n')}\n}\n`;
  return [
    `/* GENERATED by scripts/design/build-looks.mjs from looks.data.mjs — do not edit by hand. */`,
    `/* Look: ${look.name} (${id}). ${look.tagline} */`,
    '',
    block([`[data-look="${id}"]`, `[data-look="${id}"][data-mode="light"]`, `.dark [data-look="${id}"][data-mode="light"]`], 'light'),
    block([`[data-look="${id}"].dark`, `.dark [data-look="${id}"]`, `[data-look="${id}"][data-mode="dark"]`], 'dark'),
  ].join('\n');
}

export function build({ check = false, dirUrl = LOOKS_DIR_URL } = {}) {
  mkdirSync(fileURLToPath(dirUrl), { recursive: true });
  const stale = [];
  for (const look of LOOKS) {
    const url = new URL(`${look.id}.css`, dirUrl);
    const next = renderLook(look);
    const current = existsSync(url) ? readFileSync(url, 'utf8') : null;
    if (current === next) continue;
    if (check) stale.push(look.id);
    else writeFileSync(url, next);
  }
  return stale;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const check = process.argv.includes('--check');
  const stale = build({ check });
  if (check && stale.length > 0) {
    console.error(`look sheets out of date: ${stale.join(', ')} — run node scripts/design/build-looks.mjs`);
    process.exitCode = 1;
  } else {
    console.log(check ? 'look sheets up to date' : `wrote ${LOOKS.length} look sheets`);
  }
}
