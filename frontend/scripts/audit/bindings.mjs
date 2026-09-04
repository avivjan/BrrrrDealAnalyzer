/**
 * Gate G4 — behaviour manifest.
 *
 * For every SFC this records an *ordered* list of the elements that carry
 * behaviour (events, models, conditionals, loops, slots, behavioural
 * attributes) plus the file's `watch` sources and lifecycle hooks. Elements
 * with no behaviour at all are skipped, so adding, removing or nesting purely
 * presentational wrappers is invisible to the gate, while re-ordering a
 * `v-else-if` chain or renaming a handler is not.
 *
 * The Ui* primitives (Task 3.0) are the same idea one level up: a view adopts
 * them to move styling, so on an element whose tag is a primitive the collector
 * additionally ignores
 *
 *   1. a bound or static **presentational prop** (`PRESENTATIONAL_PROPS` —
 *      `variant`, `tone`, `status`, `size`, …) whose expression is
 *      side-effect-free, and
 *   2. a **slot** binding (`v-slot` / `#name`, scoped or not), which is where
 *      the copy the primitive renders now lives — on the primitive itself, and
 *      on a `<template>` whose parent element is a primitive. A `<template>`
 *      under anything else (`<VueDraggable><template #item>`) keeps its slot.
 *   3. a **static `as`** naming a tag in `PRESENTATIONAL_TAGS` (minus `label`,
 *      which has `for` semantics) — `UiSectionHeader as="h1"`, `UiCard
 *      as="section"` — because it picks the element without changing what a
 *      click, a form submit or assistive tech does. A static `as="button"`
 *      and every *bound* `:as` (its runtime target is invisible to the
 *      collector) are unaffected and stay recorded.
 *
 * Everything that could change what the app does is recorded on every tag,
 * primitive or not: `disabled|type|href|value|is|to|as` bound or static
 * (rule 3 above aside), every `v-on`, `v-model`, `v-for`, `v-show` and every
 * `v-if` / `v-else-if` / `v-else`. A presentational prop that calls, mutates
 * or interpolates (`:tone="toneFor(deal)"`) is recorded too, so it surfaces
 * as a diff and has to be justified.
 *
 * A primitive left with no recorded binding does not appear in the manifest at
 * all — exactly like a styling `div`. These are collection rules, so the
 * goldens (recorded from templates that contain no Ui* element and no slot
 * binding) are unaffected.
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

export const GOLDEN_PATH = join(GOLDEN_DIR, 'bindings.json');

const NODE_ELEMENT = 1;
const NODE_TEXT = 2;
const NODE_COMMENT = 3;
const NODE_ATTRIBUTE = 6;
const NODE_DIRECTIVE = 7;

/** Never recorded, bound or static: presentational or identity-only props. */
const IGNORED_PROPS = new Set([
  'class', 'style', 'pt', 'ptOptions', 'inputClass', 'input-class',
  'ghost-class', 'ghostClass', 'chosen-class', 'chosenClass',
  'drag-class', 'dragClass', 'id', 'for', 'role', 'key',
]);

/** Static attributes that carry behaviour and are therefore frozen. */
const BEHAVIOURAL_ATTRS = new Set([
  'type', 'href', 'target', 'rel', 'accept', 'capture', 'multiple', 'inputmode',
  'autocomplete', 'placeholder', 'title', 'tabindex', 'handle', 'group', 'animation',
  'ref', 'value', 'name', 'min', 'max', 'step', 'rows', 'maxlength', 'readonly',
  'disabled', 'checked', 'selected',
  // A Teleport/RouterLink target is behaviour, not presentation.
  'to',
  // `UiCard as="button"` renders `<component :is="as">`: it picks the element,
  // so it is behaviour on every tag — except a *static* value naming a
  // presentational tag, which `bindingFor` exempts. See
  // `ALWAYS_RECORDED_PROPS` and `PRESENTATIONAL_AS_VALUES`.
  'as',
]);

/** Purely decorative motion directives — invisible unless they take a value. */
const VALUELESS_MOTION_DIRECTIVES = new Set(['reveal', 'press', 'hover-lift', 'flash', 'count-up']);

/** Presentational component aliases collapsed to their underlying element. */
const TAG_ALIASES = { UiButton: 'button', UiIconButton: 'button' };

/**
 * The presentational primitives, and the tags they are allowed to replace.
 *
 * `UiButton`/`UiIconButton` are handled above, at collection time, because
 * they collapse to exactly one element (`button`) no matter what they replace.
 * These do not: `UiCard` may stand in for a `div`, a `section` or an `li`, so
 * there is no single tag to record. They are therefore resolved *at comparison
 * time* against the tag the golden actually holds, which keeps the goldens
 * untouched and keeps the substitution one-way:
 *
 *   golden `div`   -> current `UiCard`  equal (a wrapper swap)
 *   golden `div`   -> current `span`    still a change (neither side is a Ui*)
 *   golden `input` -> current `UiField` still a change (input is behavioural)
 *
 * Bindings are never relaxed: the alias only ever forgives the tag, and the
 * binding list must still match exactly, in order.
 */
const PRESENTATIONAL_UI = new Set([
  'UiCard', 'UiStatTile', 'UiBadge', 'UiSectionHeader', 'UiEmptyState',
  'UiSkeleton', 'UiSaveStatus', 'UiTabs', 'UiStepper', 'UiField', 'UiModalPanel',
]);

/**
 * Tags a presentational primitive may replace. Deliberately excludes every
 * native or behavioural tag — `input select textarea a form button img video
 * iframe canvas RouterLink Teleport VueDraggable` — so swapping a control for
 * a component is always a reportable change.
 */
const PRESENTATIONAL_TAGS = new Set([
  'div', 'section', 'article', 'span', 'p',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'li', 'ul', 'ol', 'dl', 'dt', 'dd', 'label', 'small', 'strong',
]);

/** Every primitive: the two that alias to `button`, plus the presentational ones. */
const UI_TAGS = new Set([...PRESENTATIONAL_UI, 'UiButton', 'UiIconButton']);

/**
 * The props the primitives take to choose an appearance. On a primitive these
 * are styling, so they are ignored exactly as `class` is; on any other tag they
 * keep whatever meaning they already had (`:required` on an `<input>` is still
 * behaviour). Both spellings are listed where a template may use either.
 */
const PRESENTATIONAL_PROPS = new Set([
  'variant', 'size', 'active', 'tone', 'dealType', 'deal-type', 'loading', 'block',
  'padding', 'icon', 'lines', 'rounded', 'status', 'count', 'compact',
  'labelledBy', 'labelled-by', 'invalid', 'required', 'inline', 'label',
  'ariaLabel', 'aria-label', 'interactive', 'hint',
]);

/**
 * Bindings recorded on every tag, primitive or not. Listed explicitly so that
 * a name added to `PRESENTATIONAL_PROPS` by mistake can never silence one.
 *
 * `as` is here, not above, because it is not styling: `UiCard` renders
 * `<component :is="as">`, so `as` picks the element the browser gets, and
 * `as="button"` changes what a click does. A use whose value could change
 * behaviour must be justified by an allowlist row (see `isAllowedAsAddition`)
 * — except a *static* value naming a presentational tag (`as="section"`,
 * `as="h1"`), which `bindingFor` does not record at all: see
 * `PRESENTATIONAL_AS_VALUES`.
 */
const ALWAYS_RECORDED_PROPS = new Set(['disabled', 'type', 'href', 'value', 'is', 'to', 'as']);

const TRANSITION_TAGS = new Set(['UiTransition', 'UiTransitionGroup', 'Transition', 'TransitionGroup']);
const TRANSITION_WRAPPER_ATTRS = new Set(['preset', 'appear', 'tag', 'name', 'mode', 'css']);

const LIFECYCLE_HOOKS = ['onMounted', 'onBeforeMount', 'onUnmounted', 'onBeforeUnmount', 'onUpdated'];

const BRANCH_KINDS = new Set(['if', 'else-if', 'else']);

/** The two ways a template can hand a primitive the element it renders. */
const AS_KINDS = new Set(['attr:as', 'bind:as']);

/**
 * Static `as` values presentational enough to leave unrecorded: every tag in
 * `PRESENTATIONAL_TAGS` except `label`, which carries `for` semantics a
 * heading or a div does not. `UiSectionHeader as="h1"` and `UiCard
 * as="section"` pick an element, but not one that changes what a click, a
 * form submit or a screen reader's landmark list does — unlike `as="button"`
 * or `as="a"`, which stay recorded, and unlike a *bound* `:as`, whose runtime
 * value the collector cannot see and which therefore always stays recorded
 * (see the `bind` case in `bindingFor`).
 */
const PRESENTATIONAL_AS_VALUES = new Set([...PRESENTATIONAL_TAGS].filter((tag) => tag !== 'label'));

function isIgnoredProp(name) {
  return IGNORED_PROPS.has(name) || name.startsWith('aria-') || name.startsWith('data-');
}

/** Vue >= 3.4 models directive modifiers as expression nodes, older ones as strings. */
function modifierNames(directive) {
  return (directive.modifiers ?? []).map((modifier) =>
    typeof modifier === 'string' ? modifier : (modifier.content ?? String(modifier)),
  );
}

function staticArgName(directive) {
  const arg = directive.arg;
  if (!arg) return null;
  return arg.isStatic === false ? `[${collapse(arg.content)}]` : collapse(arg.content);
}

function propName(prop) {
  if (prop.type === NODE_ATTRIBUTE) return prop.name;
  if (prop.type === NODE_DIRECTIVE && prop.name === 'bind') return staticArgName(prop) ?? 'bind';
  return `v-${prop.name}`;
}

function isTransitionWrapper(node) {
  if (!TRANSITION_TAGS.has(node.tag)) return false;
  return node.props.every((prop) => TRANSITION_WRAPPER_ATTRS.has(propName(prop)));
}

function binding(kind, { arg = null, modifiers = [], expression = '' } = {}) {
  return { kind, arg, modifiers, expression };
}

/**
 * True when the expression can neither call nor assign anything, so passing it
 * to a primitive cannot run code the template did not already run: identifiers,
 * member access, literals, `!x`, `&&`/`||`/`??`, ternaries and the comparisons
 * `=== !== >= <=`.
 *
 * Rejected: a call `(`, an arrow `=>`, an increment or decrement `++` / `--`,
 * a backtick (a template literal can be tagged, which is a call in disguise,
 * and interpolates arbitrary expressions), and any other `=`.
 */
function isSideEffectFree(expression) {
  if (/[(`]|=>|\+\+|--/.test(expression)) return false;
  return !expression.replace(/===|!==|>=|<=/g, '').includes('=');
}

/** True when `name` is presentational *on this tag* and therefore not recorded. */
function isPresentationalOn(tag, name, expression) {
  if (!UI_TAGS.has(tag)) return false;
  if (ALWAYS_RECORDED_PROPS.has(name)) return false;
  if (!PRESENTATIONAL_PROPS.has(name)) return false;
  return isSideEffectFree(expression);
}

/** Turn one prop into a manifest binding, or `null` when it is not behavioural. */
function bindingFor(prop, branch, tag, parentTag) {
  if (prop.type === NODE_ATTRIBUTE) {
    if (isIgnoredProp(prop.name) || !BEHAVIOURAL_ATTRS.has(prop.name)) return null;
    // Rule 1 for a static attribute. No name is in both `PRESENTATIONAL_PROPS`
    // and `BEHAVIOURAL_ATTRS` today, so this is a guard that keeps the rule
    // true if either list grows, rather than a live path. A static value can
    // neither call nor assign, so the name alone decides.
    if (isPresentationalOn(tag, prop.name, '')) return null;
    // Rule 2 for a static attribute, `as` only (round 2): a value naming a
    // presentational tag cannot change behaviour, only what the element is,
    // so it is not recorded on a primitive. A static value outside
    // `PRESENTATIONAL_AS_VALUES` (`as="button"`) and every bound `:as`
    // (the `bind` case below) are untouched by this rule.
    if (prop.name === 'as' && UI_TAGS.has(tag) && PRESENTATIONAL_AS_VALUES.has(collapse(prop.value?.content ?? ''))) {
      return null;
    }
    return binding(`attr:${prop.name}`, { expression: collapse(prop.value?.content ?? '') });
  }
  if (prop.type !== NODE_DIRECTIVE) return null;

  const expression = collapse(prop.exp?.content ?? '');
  const modifiers = modifierNames(prop);
  const arg = staticArgName(prop);

  switch (prop.name) {
    case 'bind': {
      if (arg !== null && isIgnoredProp(arg)) return null;
      if (arg !== null && isPresentationalOn(tag, arg, expression)) return null;
      return binding(arg === null ? 'bind' : `bind:${arg}`, { arg, modifiers, expression });
    }
    case 'on':
      return binding('on', { arg, modifiers, expression });
    case 'model':
      return binding('model', { arg, modifiers, expression });
    case 'slot':
      // Copy handed to a primitive through a slot is presentation, whether it
      // is named on the primitive itself (`<UiField #default>`) or on a
      // `<template>` the primitive holds (`<UiModalPanel><template #header>`).
      // A slot anywhere else is behaviour, and that includes a `<template>`
      // under a non-primitive parent: `<VueDraggable><template #item>` names
      // the row renderer, and `<RouterView v-slot>` the routed component.
      if (UI_TAGS.has(tag)) return null;
      if (tag === 'template' && UI_TAGS.has(parentTag)) return null;
      return binding('slot', { arg, modifiers, expression });
    case 'show':
    case 'for':
      return binding(prop.name, { modifiers, expression });
    case 'if':
    case 'else-if':
    case 'else':
      return { ...binding(prop.name, { modifiers, expression }), ...(branch ?? {}) };
    default: {
      if (VALUELESS_MOTION_DIRECTIVES.has(prop.name) && expression === '') return null;
      return binding(`directive:${prop.name}`, { arg, modifiers, expression });
    }
  }
}

/**
 * Map each element child to its `v-if` chain: consecutive `if` / `else-if` /
 * `else` siblings share the leading `v-if` expression as chain id, and carry
 * their 0-based ordinal within it.
 */
function branchesOf(children) {
  const branches = new Map();
  let chain = null;
  let index = 0;
  for (const child of children) {
    if (child.type === NODE_COMMENT) continue;
    if (child.type === NODE_TEXT && collapse(child.content) === '') continue;
    if (child.type !== NODE_ELEMENT) {
      chain = null;
      continue;
    }
    const directives = child.props.filter((prop) => prop.type === NODE_DIRECTIVE);
    const head = directives.find((prop) => prop.name === 'if');
    const branch = directives.find((prop) => prop.name === 'else-if' || prop.name === 'else');
    if (head) {
      chain = collapse(head.exp?.content ?? '');
      index = 0;
      branches.set(child, { chain, chainIndex: 0 });
    } else if (branch && chain !== null) {
      index += 1;
      branches.set(child, { chain, chainIndex: index });
    } else {
      chain = null;
    }
  }
  return branches;
}

/** Ordered behaviour entries for one parsed template. */
export function collectElements(descriptor) {
  const elements = [];
  walk(descriptor.template?.ast?.children ?? [], null);
  return elements;

  function walk(children, parentTag) {
    const branches = branchesOf(children);
    for (const node of children) {
      if (node.type !== NODE_ELEMENT) continue;
      if (!isTransitionWrapper(node)) {
        const bindings = node.props
          .map((prop) => bindingFor(prop, branches.get(node), node.tag, parentTag))
          .filter(Boolean);
        if (bindings.length > 0) {
          elements.push({
            tag: TAG_ALIASES[node.tag] ?? node.tag,
            line: node.loc.start.line,
            bindings,
          });
        }
      }
      walk(node.children ?? [], node.tag);
    }
  }
}

/** Read the first argument of a call, stopping at the first top-level comma. */
function readFirstArgument(text, start) {
  let depth = 0;
  let quote = null;
  let index = start;
  for (; index < text.length; index += 1) {
    const char = text[index];
    if (quote) {
      if (char === '\\') index += 1;
      else if (char === quote) quote = null;
      continue;
    }
    if (char === '"' || char === "'" || char === '`') quote = char;
    else if (char === '(' || char === '[' || char === '{') depth += 1;
    else if (char === ')' && depth === 0) break;
    else if (char === ')' || char === ']' || char === '}') depth -= 1;
    else if (char === ',' && depth === 0) break;
  }
  return text.slice(start, index);
}

/** Whitespace-collapsed first arguments of every `watch(` / `watchEffect(` call. */
export function collectWatches(scriptText) {
  const found = [];
  const pattern = /(^|[^\w.$])(watch|watchEffect)\s*\(/g;
  let match;
  while ((match = pattern.exec(scriptText)) !== null) {
    found.push(collapse(readFirstArgument(scriptText, match.index + match[0].length)));
  }
  return found;
}

/** Which of the frozen lifecycle hooks the file registers, in a fixed order. */
export function collectHooks(scriptText) {
  return LIFECYCLE_HOOKS.filter((hook) =>
    new RegExp(`(^|[^\\w.$])${hook}\\s*\\(`).test(scriptText),
  );
}

export function manifestFromDescriptor(descriptor) {
  const scriptText = `${descriptor.scriptSetup?.content ?? ''}\n${descriptor.script?.content ?? ''}`;
  return {
    elements: collectElements(descriptor),
    watches: collectWatches(scriptText),
    hooks: collectHooks(scriptText),
  };
}

export function manifestFromSource(source, file) {
  return manifestFromDescriptor(parseSfcSource(source, file).descriptor);
}

export function manifestFromFile(root, file) {
  return manifestFromDescriptor(parseSfc(join(root, file), file).descriptor);
}

export function buildGolden(root = FRONTEND_ROOT) {
  const golden = {};
  for (const file of listSfcFiles(root)) golden[file] = manifestFromFile(root, file);
  return golden;
}

/** The compared form of an entry — deliberately free of line numbers. */
export function canonical(entry) {
  return JSON.stringify({ tag: entry.tag, bindings: entry.bindings });
}

/** True when `currentTag` is a presentational primitive standing in for `goldenTag`. */
function tagsMatch(goldenTag, currentTag) {
  if (goldenTag === currentTag) return true;
  return PRESENTATIONAL_UI.has(currentTag) && PRESENTATIONAL_TAGS.has(goldenTag);
}

/**
 * The comparator the diff runs on. Same equality as `canonical`, except that
 * the tag is resolved against the pair rather than in isolation.
 */
export function entriesMatch(goldenEntry, currentEntry) {
  return (
    tagsMatch(goldenEntry.tag, currentEntry.tag) &&
    JSON.stringify(goldenEntry.bindings) === JSON.stringify(currentEntry.bindings)
  );
}

function isBranchOnlyEntry(entry) {
  return entry.bindings.length > 0 && entry.bindings.every((b) => BRANCH_KINDS.has(b.kind));
}

function branchExpression(entry) {
  return collapse(entry.bindings.map((b) => b.expression ?? '').join(' '));
}

/**
 * The one-time `App.vue` rewrite the plan approves:
 *
 *   <RouterView v-slot="{ Component }">
 *     <UiTransition preset="page" appear><component :is="Component" /></UiTransition>
 *   </RouterView>
 *
 * It is an exact-match whitelist of the two entries that rewrite adds (the
 * transition itself is a wrapper and is never recorded), not a tag-based class:
 * anything else under the same reason must fail.
 */
const ROUTERVIEW_SLOT_REASON = 'routerview-transition-slot';
const ROUTERVIEW_SLOT_FILE = 'src/App.vue';
const ROUTERVIEW_SLOT_ADDITIONS = new Set([
  JSON.stringify({
    tag: 'RouterView',
    bindings: [{ kind: 'slot', arg: null, modifiers: [], expression: '{ Component }' }],
  }),
  JSON.stringify({
    tag: 'component',
    bindings: [{ kind: 'bind:is', arg: 'is', modifiers: [], expression: 'Component' }],
  }),
]);

function allowlistFor(allowlist, file) {
  return (allowlist.bindings ?? []).filter((entry) => entry.file === file);
}

/**
 * A new presentational `v-if` chain, admitted only by a row that names the
 * exact expression. A row without an `expression`, or an entry with none of its
 * own (a bare `v-else`), never matches: a reason alone must not open the gate.
 */
function isAllowedBranchAddition(entry, fileAllowlist) {
  if (!isBranchOnlyEntry(entry)) return false;
  const expression = branchExpression(entry);
  if (expression === '') return false;
  return fileAllowlist.some(
    (allowed) =>
      typeof allowed.expression === 'string' && collapse(allowed.expression) === expression,
  );
}

/**
 * A new element whose only binding is the `as` a primitive renders through
 * `<component :is>`, admitted by a row that names the tag and that exact
 * binding, in the compact `kind=expression` form:
 *
 *   { file, tag: 'UiCard', bindings: ['attr:as=section'], reason: '…' }
 *
 * Same shape as the branch-only rule above: a row without a `bindings` list
 * never matches, so a reason alone cannot open the gate, and the tag is the one
 * the manifest records (a `UiButton` is recorded as `button`).
 */
function isAllowedAsAddition(entry, fileAllowlist) {
  if (entry.bindings.length === 0) return false;
  if (!entry.bindings.every((b) => AS_KINDS.has(b.kind))) return false;
  const keys = entry.bindings.map((b) => `${b.kind}=${collapse(b.expression ?? '')}`);
  return fileAllowlist.some(
    (allowed) =>
      allowed.tag === entry.tag &&
      Array.isArray(allowed.bindings) &&
      allowed.bindings.length === keys.length &&
      allowed.bindings.every((name, index) => collapse(name) === keys[index]),
  );
}

function isRouterViewSlotAddition(file, entry, fileAllowlist) {
  if (file !== ROUTERVIEW_SLOT_FILE) return false;
  if (!fileAllowlist.some((allowed) => allowed.reason === ROUTERVIEW_SLOT_REASON)) return false;
  return ROUTERVIEW_SLOT_ADDITIONS.has(canonical(entry));
}

function isAllowedAddition(file, entry, fileAllowlist) {
  return (
    isAllowedBranchAddition(entry, fileAllowlist) ||
    isAllowedAsAddition(entry, fileAllowlist) ||
    isRouterViewSlotAddition(file, entry, fileAllowlist)
  );
}

/**
 * Diff two ordered entry lists, pairing an adjacent removal + reportable
 * addition into a single "changed" report so the output names the golden and
 * current lines. Allowlisted additions are set aside *before* pairing, so an
 * accepted addition can never disguise a removal as a rename.
 */
export function diffElements(file, goldenElements, currentElements, fileAllowlist) {
  const parts = diffArrays(goldenElements, currentElements, { comparator: entriesMatch });
  const lines = [];
  let goldenIndex = 0;
  let currentIndex = 0;

  for (let part = 0; part < parts.length; part += 1) {
    const chunk = parts[part];
    if (!chunk.added && !chunk.removed) {
      goldenIndex += chunk.value.length;
      currentIndex += chunk.value.length;
      continue;
    }

    let removed = [];
    let added = [];
    if (chunk.removed) {
      removed = goldenElements.slice(goldenIndex, goldenIndex + chunk.value.length);
      goldenIndex += chunk.value.length;
      const next = parts[part + 1];
      if (next?.added) {
        added = currentElements.slice(currentIndex, currentIndex + next.value.length);
        currentIndex += next.value.length;
        part += 1;
      }
    } else {
      added = currentElements.slice(currentIndex, currentIndex + chunk.value.length);
      currentIndex += chunk.value.length;
    }

    const reportable = added.filter((entry) => !isAllowedAddition(file, entry, fileAllowlist));
    const pairs = Math.min(removed.length, reportable.length);
    for (let index = 0; index < pairs; index += 1) {
      lines.push(changedElementLine(file, removed[index], reportable[index]));
    }
    lines.push(...removed.slice(pairs).map((entry) => removedElementLine(file, entry)));
    lines.push(...reportable.slice(pairs).map((entry) => addedElementLine(file, entry)));
  }

  return lines;
}

function changedElementLine(file, before, after) {
  return {
    level: 'FAIL',
    text:
      `${file} changed element (golden L${before.line} -> current L${after.line}) ` +
      `${canonical(before)} => ${canonical(after)}`,
  };
}

/** A removed behavioural element is always a failure; no allowlist row admits one. */
function removedElementLine(file, entry) {
  return {
    level: 'FAIL',
    text: `${file} removed element (golden L${entry.line}) ${canonical(entry)}`,
  };
}

function addedElementLine(file, entry) {
  return {
    level: 'FAIL',
    text: `${file} added element (current L${entry.line}) ${canonical(entry)}`,
  };
}

export function verifyBindings({ golden, current, allowlist }) {
  const lines = [];

  for (const file of Object.keys(current).sort()) {
    if (!(file in golden)) lines.push({ level: 'INFO', text: `${file} new file, not frozen` });
  }

  for (const file of Object.keys(golden).sort()) {
    const currentManifest = current[file];
    if (!currentManifest) {
      lines.push({ level: 'FAIL', text: `${file} deleted frozen file` });
      continue;
    }
    const goldenManifest = golden[file];
    lines.push(
      ...diffElements(
        file,
        goldenManifest.elements,
        currentManifest.elements,
        allowlistFor(allowlist, file),
      ),
    );
    for (const key of ['watches', 'hooks']) {
      const before = JSON.stringify(goldenManifest[key] ?? []);
      const after = JSON.stringify(currentManifest[key] ?? []);
      if (before !== after) {
        lines.push({ level: 'FAIL', text: `${file} ${key} changed: ${before} => ${after}` });
      }
    }
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
      lines: [
        { level: 'INFO', text: `wrote golden/bindings.json (${Object.keys(golden).length} files)` },
      ],
    };
  }
  const { golden, missing } = loadGolden(GOLDEN_PATH);
  if (missing) return missingGoldenResult('bindings.json');
  const current = {};
  for (const file of listSfcFiles(root)) current[file] = manifestFromFile(root, file);
  return verifyBindings({ golden, current, allowlist: readAllowlist() });
}

if (isCliEntry(import.meta.url)) {
  reportGate('G4', run({ write: process.argv.includes('--write') }));
}
