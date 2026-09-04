/**
 * Gate G4 — behaviour manifest.
 *
 * For every SFC this records an *ordered* list of the elements that carry
 * behaviour (events, models, conditionals, loops, slots, behavioural
 * attributes) plus the file's `watch` sources and lifecycle hooks. Elements
 * with no behaviour at all are skipped, so adding, removing or nesting purely
 * presentational wrappers is invisible to the gate, while re-ordering a
 * `v-else-if` chain or renaming a handler is not.
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
]);

/** Purely decorative motion directives — invisible unless they take a value. */
const VALUELESS_MOTION_DIRECTIVES = new Set(['reveal', 'press', 'hover-lift', 'flash', 'count-up']);

/** Presentational component aliases collapsed to their underlying element. */
const TAG_ALIASES = { UiButton: 'button', UiIconButton: 'button' };

const TRANSITION_TAGS = new Set(['UiTransition', 'UiTransitionGroup', 'Transition', 'TransitionGroup']);
const TRANSITION_WRAPPER_ATTRS = new Set(['preset', 'appear', 'tag', 'name', 'mode', 'css']);

const LIFECYCLE_HOOKS = ['onMounted', 'onBeforeMount', 'onUnmounted', 'onBeforeUnmount', 'onUpdated'];

const BRANCH_KINDS = new Set(['if', 'else-if', 'else']);

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

/** Turn one prop into a manifest binding, or `null` when it is not behavioural. */
function bindingFor(prop, branch) {
  if (prop.type === NODE_ATTRIBUTE) {
    if (isIgnoredProp(prop.name) || !BEHAVIOURAL_ATTRS.has(prop.name)) return null;
    return binding(`attr:${prop.name}`, { expression: collapse(prop.value?.content ?? '') });
  }
  if (prop.type !== NODE_DIRECTIVE) return null;

  const expression = collapse(prop.exp?.content ?? '');
  const modifiers = modifierNames(prop);
  const arg = staticArgName(prop);

  switch (prop.name) {
    case 'bind': {
      if (arg !== null && isIgnoredProp(arg)) return null;
      return binding(arg === null ? 'bind' : `bind:${arg}`, { arg, modifiers, expression });
    }
    case 'on':
      return binding('on', { arg, modifiers, expression });
    case 'model':
      return binding('model', { arg, modifiers, expression });
    case 'slot':
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
  walk(descriptor.template?.ast?.children ?? []);
  return elements;

  function walk(children) {
    const branches = branchesOf(children);
    for (const node of children) {
      if (node.type !== NODE_ELEMENT) continue;
      if (!isTransitionWrapper(node)) {
        const bindings = node.props
          .map((prop) => bindingFor(prop, branches.get(node)))
          .filter(Boolean);
        if (bindings.length > 0) {
          elements.push({
            tag: TAG_ALIASES[node.tag] ?? node.tag,
            line: node.loc.start.line,
            bindings,
          });
        }
      }
      walk(node.children ?? []);
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

function isBranchOnlyEntry(entry) {
  return entry.bindings.length > 0 && entry.bindings.every((b) => BRANCH_KINDS.has(b.kind));
}

function branchExpression(entry) {
  return collapse(entry.bindings.map((b) => b.expression ?? '').join(' '));
}

/** Entries the `routerview-transition-slot` reason covers on both sides of the diff. */
function isRouterViewSlotEntry(entry) {
  return (
    TRANSITION_TAGS.has(entry.tag) ||
    entry.tag === 'RouterView' ||
    entry.tag === 'component' ||
    entry.bindings.some((b) => b.kind === 'slot')
  );
}

function allowlistFor(allowlist, file) {
  return (allowlist.bindings ?? []).filter((entry) => entry.file === file);
}

function isAllowedAddition(entry, fileAllowlist) {
  if (
    isBranchOnlyEntry(entry) &&
    fileAllowlist.some((allowed) => collapse(allowed.expression ?? '') === branchExpression(entry))
  ) {
    return true;
  }
  return (
    isRouterViewSlotEntry(entry) &&
    fileAllowlist.some((allowed) => allowed.reason === 'routerview-transition-slot')
  );
}

function isAllowedRemoval(entry, fileAllowlist) {
  return (
    isRouterViewSlotEntry(entry) &&
    fileAllowlist.some((allowed) => allowed.reason === 'routerview-transition-slot')
  );
}

/**
 * Diff two ordered entry lists, pairing an adjacent removal + addition into a
 * single "changed" report so the output names the golden and current lines.
 */
export function diffElements(file, goldenElements, currentElements, fileAllowlist) {
  const parts = diffArrays(goldenElements.map(canonical), currentElements.map(canonical));
  const lines = [];
  let goldenIndex = 0;
  let currentIndex = 0;

  for (let part = 0; part < parts.length; part += 1) {
    const current = parts[part];
    if (!current.added && !current.removed) {
      goldenIndex += current.value.length;
      currentIndex += current.value.length;
      continue;
    }
    if (current.removed) {
      const next = parts[part + 1];
      const removed = goldenElements.slice(goldenIndex, goldenIndex + current.value.length);
      goldenIndex += current.value.length;
      if (next?.added) {
        const added = currentElements.slice(currentIndex, currentIndex + next.value.length);
        currentIndex += next.value.length;
        part += 1;
        const pairs = Math.min(removed.length, added.length);
        for (let i = 0; i < pairs; i += 1) {
          lines.push({
            level: 'FAIL',
            text:
              `${file} changed element (golden L${removed[i].line} -> current L${added[i].line}) ` +
              `${canonical(removed[i])} => ${canonical(added[i])}`,
          });
        }
        lines.push(...reportExtraRemovals(file, removed.slice(pairs), fileAllowlist));
        lines.push(...reportExtraAdditions(file, added.slice(pairs), fileAllowlist));
        continue;
      }
      lines.push(...reportExtraRemovals(file, removed, fileAllowlist));
      continue;
    }
    const added = currentElements.slice(currentIndex, currentIndex + current.value.length);
    currentIndex += current.value.length;
    lines.push(...reportExtraAdditions(file, added, fileAllowlist));
  }

  return lines;
}

function reportExtraRemovals(file, removed, fileAllowlist) {
  return removed
    .filter((entry) => !isAllowedRemoval(entry, fileAllowlist))
    .map((entry) => ({
      level: 'FAIL',
      text: `${file} removed element (golden L${entry.line}) ${canonical(entry)}`,
    }));
}

function reportExtraAdditions(file, added, fileAllowlist) {
  return added
    .filter((entry) => !isAllowedAddition(entry, fileAllowlist))
    .map((entry) => ({
      level: 'FAIL',
      text: `${file} added element (current L${entry.line}) ${canonical(entry)}`,
    }));
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
