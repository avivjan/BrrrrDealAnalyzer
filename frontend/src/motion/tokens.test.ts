// @vitest-environment node
/// <reference types="node" />
// `tsconfig.app.json` scopes `types` to `vite/client` because the app itself is
// a browser bundle; this is a Node-environment test, so it pulls the Node types
// in explicitly. (`tokens.css?raw` is not an option: Vitest replaces every CSS
// import with an empty string unless `test.css` is enabled.)
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

import { DUR, EASE } from './tokens';

/** The CSS these constants mirror, read from disk at test time. */
const tokensCss = readFileSync(new URL('../assets/tokens.css', import.meta.url), 'utf8');

/** Every `--<prefix>-*` declaration in `tokens.css`, keyed by its suffix. */
function declarations(prefix: string): Record<string, string> {
  const found: Record<string, string> = {};
  const pattern = new RegExp(`--${prefix}-([\\w-]+)\\s*:\\s*([^;]+);`, 'g');
  for (const match of tokensCss.matchAll(pattern)) {
    const [, name, value] = match;
    if (name === undefined || value === undefined) continue;
    found[name] = value.trim();
  }
  return found;
}

describe('motion tokens', () => {
  it('exposes the three durations in seconds, as GSAP wants them', () => {
    expect(DUR).toEqual({ fast: 0.15, base: 0.25, slow: 0.4 });
  });

  it('exposes the three eases as GSAP ease names', () => {
    expect(EASE).toEqual({
      standard: 'power2.out',
      emphasized: 'power3.inOut',
      exit: 'power1.in',
    });
  });
});

describe('the mirror of tokens.css', () => {
  it('covers exactly the durations tokens.css declares', () => {
    expect(Object.keys(DUR).sort()).toEqual(Object.keys(declarations('dur')).sort());
  });

  it('matches each duration, second-for-millisecond', () => {
    const css = declarations('dur');
    for (const [name, seconds] of Object.entries(DUR)) {
      expect(css[name], `--dur-${name}`).toBe(`${Math.round(seconds * 1000)}ms`);
    }
  });

  it('covers exactly the eases tokens.css declares', () => {
    expect(Object.keys(EASE).sort()).toEqual(Object.keys(declarations('ease')).sort());
  });

  it('pairs every ease name with a cubic-bezier in tokens.css', () => {
    const css = declarations('ease');
    for (const name of Object.keys(EASE)) {
      expect(css[name], `--ease-${name}`).toMatch(/^cubic-bezier\(/);
    }
  });
});
