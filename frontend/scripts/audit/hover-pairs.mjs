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
 * `REVEAL_PAIRS` lists every way this codebase may reveal a control on hover,
 * each with the counterpart that reveal specifically needs: opacity, visibility,
 * the three display switches and `pointer-events`. Making a control *visible*
 * with `touch:opacity-100` does not undo a `hover:flex`, so each reveal is
 * checked against its own counterpart rather than against the set.
 *
 * Scans the template AST of every `src/**\/*.vue`, reading each element's class
 * text — static `class`, bound `:class`, or both concatenated. The two sides are
 * matched differently, on purpose:
 *
 * - A **reveal** matches a class token that *ends with* the key, so
 *   `hover:opacity-100`, `group-hover:opacity-100`, `peer-hover:opacity-100` and
 *   `md:group-hover:opacity-100` are all caught, while `hover:flex-col` — which
 *   contains `hover:flex` but reveals nothing — is not.
 * - A **counterpart** must be a whole class token, so `md:touch:opacity-100`,
 *   which only applies from `md` up, does not satisfy `touch:opacity-100`.
 *
 * `focus-within:*` is a keyboard affordance, not a touch one, so it never
 * satisfies the rule on its own.
 *
 * Bound classes are matched as raw expression text rather than evaluated: an
 * array, ternary or object literal all mention the class they would apply, and a
 * class the expression cannot produce is a dead string, not a false failure. The
 * consequence is deliberate: a ternary whose two branches are mutually exclusive
 * (`a ? 'group-hover:opacity-100' : 'touch:opacity-100'`) counts as paired, because
 * a gate that reads text cannot tell a real pair from an either/or one, and
 * failing every legitimate conditional would be the worse error.
 */
import { join } from 'node:path';
import { FRONTEND_ROOT, isCliEntry, listSfcFiles, parseSfc, parseSfcSource } from './sfc.mjs';

/**
 * `[reveal, counterpart]` — a way to reveal a control on hover, and the `touch:`
 * utility that has to undo it. Add a row here when a view starts revealing a
 * control some other way.
 */
export const REVEAL_PAIRS = [
  ['hover:opacity-100', 'touch:opacity-100'],
  ['hover:visible', 'touch:visible'],
  ['hover:flex', 'touch:flex'],
  ['hover:block', 'touch:block'],
  ['hover:inline-flex', 'touch:inline-flex'],
  ['hover:pointer-events-auto', 'touch:pointer-events-auto'],
];

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

/**
 * Class text split into candidate class names. Whitespace and quotes are the
 * separators, which is enough to isolate the class names inside a `:class`
 * array, ternary or object literal; the punctuation left over between them
 * (`{`, `,`, `:`) simply never equals a utility.
 */
export function classTokens(text) {
  return text.split(/['"\s]+/).filter(Boolean);
}

/** The counterparts an element reveals with but does not pair, in table order. */
export function missingCounterparts(text) {
  const tokens = classTokens(text);
  const missing = [];
  for (const [reveal, counterpart] of REVEAL_PAIRS) {
    const reveals = tokens.some((token) => token.endsWith(reveal));
    if (reveals && !tokens.includes(counterpart)) missing.push(counterpart);
  }
  return missing;
}

/** `{ level, text }` lines for every element that reveals on hover only. */
export function findUnpaired(descriptor, file) {
  const lines = [];
  walk(descriptor.template?.ast?.children ?? []);
  return lines;

  function walk(children) {
    for (const node of children) {
      if (node.type === NODE_ELEMENT) {
        const missing = missingCounterparts(classText(node));
        if (missing.length > 0) {
          lines.push({
            level: 'FAIL',
            text: `${file}:${node.loc.start.line} <${node.tag}> reveals on hover without ${missing.join(', ')}`,
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
      ? `PASS G-HOVER every hover reveal in ${result.checked} SFCs pairs with its touch: counterpart`
      : `FAIL G-HOVER ${result.lines.length} element(s) reveal on hover without a touch: counterpart`,
  );
  if (!result.ok) process.exitCode = 1;
}
