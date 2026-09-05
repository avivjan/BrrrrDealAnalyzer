/**
 * Every `data-testid` the e2e suite asks for exists in some `.vue` template.
 *
 * The hooks are the contract between the specs and the redesign: a template
 * may be rebuilt from scratch, but a hook a spec selects must come out the
 * other side. This is a one-second static check that runs in `npm test`, so a
 * lost hook is caught at the task's own gate rather than by the five-minute
 * browser suite at the phase end.
 *
 * What counts as a reference (in `e2e/**\/*.ts`):
 *   - `getByTestId('x')` and `getByTestId(\`x.${…}\`)` (the literal prefix)
 *   - `[data-testid="x"]` selectors, including escaped quotes inside strings
 *   - any single-quoted literal shaped like a hook, `area.element[.sub…]`,
 *     which is how the a11y spec's ROUTES table names each route's ready hook
 * What counts as production (in `src/**\/*.vue`):
 *   - `data-testid="x"` (static)
 *   - `:data-testid="\`x.${…}\`"` (the literal prefix before the first `${`)
 *
 * A static reference is satisfied by an equal static hook, or by a dynamic
 * hook whose prefix it starts with. A dynamic reference (prefix) is satisfied
 * when it and some dynamic hook prefix share a leading segment either way.
 * Suffix selectors (`data-testid$="…"`) are not references to one hook and
 * are ignored.
 */
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const FRONTEND_ROOT = join(__dirname, '..', '..');
const E2E_ROOT = join(FRONTEND_ROOT, 'e2e');
const SRC_ROOT = join(FRONTEND_ROOT, 'src');

function filesUnder(root: string, ext: string): string[] {
  return readdirSync(root, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(ext))
    .map((entry) => join(entry.parentPath, entry.name));
}

export interface HookReference {
  id: string;
  /** True when the spec built the id with a template literal: `id` is its prefix. */
  dynamic: boolean;
  file: string;
}

/**
 * Dotted literals that are not hooks. `bw.*` are the appearance storage keys
 * (`src/design/theme.ts`), which the theme spec reads from `localStorage`.
 */
const NOT_HOOKS = /^bw\./;

export function referencesIn(source: string, file: string): HookReference[] {
  const refs: HookReference[] = [];
  const add = (raw: string) => {
    const cut = raw.indexOf('${');
    const dynamic = cut >= 0;
    const id = dynamic ? raw.slice(0, cut) : raw;
    if (id.length > 0 && !NOT_HOOKS.test(id)) refs.push({ id, dynamic, file });
  };
  for (const match of source.matchAll(/getByTestId\(\s*(['"`])([^'"`]*)\1/g)) add(match[2]!);
  for (const match of source.matchAll(/data-testid=\\?["']([^"'\\\]]*)/g)) add(match[1]!);
  for (const match of source.matchAll(/'([a-z]+(?:\.[A-Za-z0-9_-]+)+)'/g)) add(match[1]!);
  return refs;
}

export interface ProducedHook {
  id: string;
  dynamic: boolean;
  file: string;
}

export function hooksIn(template: string, file: string): ProducedHook[] {
  const hooks: ProducedHook[] = [];
  for (const match of template.matchAll(/(?<![:\w])data-testid="([^"]+)"/g)) {
    hooks.push({ id: match[1]!, dynamic: false, file });
  }
  for (const match of template.matchAll(/:data-testid="`([^`]*)`"/g)) {
    const raw = match[1]!;
    const cut = raw.indexOf('${');
    hooks.push({ id: cut >= 0 ? raw.slice(0, cut) : raw, dynamic: cut >= 0, file });
  }
  return hooks;
}

export function isSatisfied(ref: HookReference, produced: ProducedHook[]): boolean {
  return produced.some((hook) => {
    if (!hook.dynamic && !ref.dynamic) return hook.id === ref.id;
    if (hook.dynamic && !ref.dynamic) return ref.id.startsWith(hook.id);
    // A dynamic reference matches a dynamic hook when one prefix extends the other.
    return hook.id.startsWith(ref.id) || ref.id.startsWith(hook.id);
  });
}

describe('hook inventory', () => {
  const specFiles = filesUnder(E2E_ROOT, '.ts').filter((file) => !file.includes('/node_modules/'));
  const sfcFiles = filesUnder(SRC_ROOT, '.vue');
  const produced = sfcFiles.flatMap((file) => hooksIn(readFileSync(file, 'utf8'), relative(FRONTEND_ROOT, file)));
  const referenced = specFiles.flatMap((file) =>
    referencesIn(readFileSync(file, 'utf8'), relative(FRONTEND_ROOT, file)),
  );

  it('sees the suite and the templates', () => {
    expect(specFiles.length).toBeGreaterThan(15);
    expect(produced.length).toBeGreaterThan(300);
    expect(referenced.length).toBeGreaterThan(100);
  });

  it('finds every hook the e2e suite references in some template', () => {
    const missing = new Map<string, Set<string>>();
    for (const ref of referenced) {
      if (isSatisfied(ref, produced)) continue;
      const key = ref.dynamic ? `${ref.id}\${…}` : ref.id;
      if (!missing.has(key)) missing.set(key, new Set());
      missing.get(key)!.add(ref.file);
    }
    const report = [...missing.entries()]
      .map(([id, files]) => `  ${id}  ← ${[...files].join(', ')}`)
      .join('\n');
    expect(missing.size, `hooks referenced by the e2e suite but produced by no template:\n${report}`).toBe(0);
  });
});

describe('hook inventory — the extractors', () => {
  it('reads static, template-literal and selector references, plus bare hook literals', () => {
    const source = [
      "page.getByTestId('mydeals.modal')",
      'page.getByTestId(`mydeals.card.${deal.id}`)',
      "page.locator('[data-testid=\"form.field.arv\"] input')",
      'page.locator(`[data-testid="${id}"]`)',
      "['my-deals', '/my-deals', 'mydeals.add-deal']",
      "expect(text).toContain('e.g')",
      "localStorage.getItem('bw.look')",
    ].join('\n');
    expect(referencesIn(source, 'spec').map((r) => [r.id, r.dynamic])).toEqual([
      ['mydeals.modal', false],
      ['mydeals.card.', true],
      ['form.field.arv', false],
      ['mydeals.modal', false],
      ['mydeals.add-deal', false],
      ['e.g', false],
    ]);
  });

  it('reads static and template-literal hooks from a template', () => {
    const template = '<div data-testid="mydeals.modal" :data-testid="`mydeals.card.${deal.id}`"></div>';
    expect(hooksIn(template, 'x.vue').map((h) => [h.id, h.dynamic])).toEqual([
      ['mydeals.modal', false],
      ['mydeals.card.', true],
    ]);
  });

  it('matches a static reference to a dynamic hook by prefix, and dynamic to dynamic either way', () => {
    const produced = [
      { id: 'mydeals.card.', dynamic: true, file: 'a' },
      { id: 'landing.offer', dynamic: false, file: 'b' },
    ];
    expect(isSatisfied({ id: 'mydeals.card.42', dynamic: false, file: 's' }, produced)).toBe(true);
    expect(isSatisfied({ id: 'mydeals.card.', dynamic: true, file: 's' }, produced)).toBe(true);
    expect(isSatisfied({ id: 'landing.offer', dynamic: false, file: 's' }, produced)).toBe(true);
    expect(isSatisfied({ id: 'landing.offer.x', dynamic: false, file: 's' }, produced)).toBe(false);
    expect(isSatisfied({ id: 'mydeals.stage.', dynamic: true, file: 's' }, produced)).toBe(false);
  });
});
