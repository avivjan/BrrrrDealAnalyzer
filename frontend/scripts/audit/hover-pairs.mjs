#!/usr/bin/env node
/**
 * Gate G-HOVER — every hover-only reveal has a touch counterpart.
 *
 * `tailwind.config.js` enables `future.hoverOnlyWhenSupported`, which wraps
 * every `hover:` utility in `@media (hover: hover)`. A control revealed only by
 * `group-hover:opacity-100` would then stay at `opacity: 0` forever on a touch
 * device — still clickable, so no Playwright actionability check and no axe run
 * can see it. The only thing that keeps those controls reachable is the
 * `touch:opacity-100` (`@media (hover: none)`) sibling on the same element, and
 * this gate is what proves it is there.
 *
 * Scans the template AST of every `src/**\/*.vue`: any element whose class —
 * static `class`, bound `:class`, or both together — mentions
 * `hover:opacity-100` (which `group-hover:opacity-100` contains) must also
 * mention `touch:opacity-100`. `focus-within:opacity-100` is a keyboard
 * affordance, not a touch one, so it never satisfies the rule on its own.
 *
 * The bound form is matched as raw expression text rather than evaluated: an
 * array, ternary or object literal all mention the class they would apply, and
 * a class the expression cannot produce is a dead string, not a false failure.
 */
import { join } from 'node:path';
import { FRONTEND_ROOT, isCliEntry, listSfcFiles, parseSfc, parseSfcSource } from './sfc.mjs';

/** The reveal that stops working on touch once the flag is on. */
export const HOVER_REVEAL = 'hover:opacity-100';
/** The counterpart it must be paired with (`@media (hover: none)`). */
export const TOUCH_REVEAL = 'touch:opacity-100';

const NODE_ELEMENT = 1;
const ATTR_STATIC = 6;
const ATTR_DIRECTIVE = 7;

/** Every class source of one element, joined: `class="…"` plus `:class="…"`. */
export function classText(node) {
  const parts = [];
  for (const prop of node.props ?? []) {
    if (prop.type === ATTR_STATIC && prop.name === 'class') {
      parts.push(prop.value?.content ?? '');
    } else if (
      prop.type === ATTR_DIRECTIVE &&
      prop.name === 'bind' &&
      prop.arg?.content === 'class'
    ) {
      parts.push(prop.exp?.content ?? '');
    }
  }
  return parts.join(' ');
}

/** `{ level, text }` lines for every element that reveals on hover only. */
export function findUnpaired(descriptor, file) {
  const lines = [];
  walk(descriptor.template?.ast?.children ?? []);
  return lines;

  function walk(children) {
    for (const node of children) {
      if (node.type === NODE_ELEMENT) {
        const classes = classText(node);
        if (classes.includes(HOVER_REVEAL) && !classes.includes(TOUCH_REVEAL)) {
          lines.push({
            level: 'FAIL',
            text: `${file}:${node.loc.start.line} <${node.tag}> reveals on hover without ${TOUCH_REVEAL}`,
          });
        }
      }
      if (Array.isArray(node.children)) walk(node.children);
    }
  }
}

export function findUnpairedInSource(source, file) {
  return findUnpaired(parseSfcSource(source, file).descriptor, file);
}

export function findUnpairedInFile(root, file) {
  return findUnpaired(parseSfc(join(root, file), file).descriptor, file);
}

export function run({ root = FRONTEND_ROOT } = {}) {
  const lines = [];
  let checked = 0;
  for (const file of listSfcFiles(root)) {
    checked += 1;
    lines.push(...findUnpairedInFile(root, file));
  }
  return { ok: lines.length === 0, checked, lines };
}

if (isCliEntry(import.meta.url)) {
  const result = run();
  for (const line of result.lines) console.log(`${line.level} G-HOVER ${line.text}`);
  console.log(
    result.ok
      ? `PASS G-HOVER every hover reveal in ${result.checked} SFCs pairs with ${TOUCH_REVEAL}`
      : `FAIL G-HOVER ${result.lines.length} hover reveal(s) without ${TOUCH_REVEAL}`,
  );
  if (!result.ok) process.exitCode = 1;
}
