// @vitest-environment node
/// <reference types="node" />
// `tsconfig.app.json` scopes `types` to `vite/client` because the app itself is
// a browser bundle; this is a Node-environment test, so it pulls the Node types
// in explicitly. (`tokens.css?raw` is not an option: Vitest replaces every CSS
// import with an empty string unless `test.css` is enabled.)
import { readFileSync } from 'node:fs';
import { afterEach, describe, expect, it } from 'vitest';

import { DUR, EASE, FALLBACK_DUR, FALLBACK_EASE, parseSeconds, resetMotionTokenCache } from './tokens';

/** The CSS the fallbacks mirror, read from disk at test time. */
const tokensCss = readFileSync(new URL('../assets/tokens.css', import.meta.url), 'utf8');

/** Every `--<prefix>-*` declaration in the `:root` block of `tokens.css`, keyed by its suffix. */
function declarations(prefix: string): Record<string, string> {
  const root = tokensCss.slice(tokensCss.indexOf(':root {'), tokensCss.indexOf('\n}', tokensCss.indexOf(':root {')));
  const found: Record<string, string> = {};
  const pattern = new RegExp(`--${prefix}-([\\w-]+)\\s*:\\s*([^;]+);`, 'g');
  for (const match of root.matchAll(pattern)) {
    const [, name, value] = match;
    if (name === undefined || value === undefined) continue;
    found[name] = value.trim();
  }
  return found;
}

afterEach(() => {
  resetMotionTokenCache();
  Reflect.deleteProperty(globalThis, 'document');
  Reflect.deleteProperty(globalThis, 'getComputedStyle');
});

describe('motion tokens without a document', () => {
  it('answer with the base values, in seconds and as GSAP ease names', () => {
    expect(typeof document).toBe('undefined');
    expect({ fast: DUR.fast, base: DUR.base, slow: DUR.slow }).toEqual({ fast: 0.15, base: 0.25, slow: 0.4 });
    expect({ standard: EASE.standard, emphasized: EASE.emphasized, exit: EASE.exit }).toEqual({
      standard: 'power2.out',
      emphasized: 'power3.inOut',
      exit: 'power1.in',
    });
  });
});

describe('the mirror of tokens.css :root', () => {
  it('covers exactly the durations tokens.css declares', () => {
    expect(Object.keys(FALLBACK_DUR).sort()).toEqual(Object.keys(declarations('dur')).sort());
  });

  it('matches each duration, second-for-millisecond', () => {
    const css = declarations('dur');
    for (const [name, seconds] of Object.entries(FALLBACK_DUR)) {
      expect(css[name], `--dur-${name}`).toBe(`${Math.round(seconds * 1000)}ms`);
    }
  });

  it('covers exactly the GSAP eases tokens.css declares, and each pairs with a cubic-bezier', () => {
    const gsap = declarations('gsap-ease');
    const css = declarations('ease');
    expect(Object.keys(FALLBACK_EASE).sort()).toEqual(Object.keys(gsap).sort());
    for (const [name, value] of Object.entries(FALLBACK_EASE)) {
      expect(gsap[name], `--gsap-ease-${name}`).toBe(value);
      expect(css[name], `--ease-${name}`).toMatch(/^cubic-bezier\(/);
    }
  });
});

describe('parseSeconds', () => {
  it('reads ms and s, and refuses anything else', () => {
    expect(parseSeconds('180ms')).toBeCloseTo(0.18);
    expect(parseSeconds('0.4s')).toBeCloseTo(0.4);
    expect(parseSeconds(' 250ms ')).toBeNaN();
    expect(parseSeconds('fast')).toBeNaN();
    expect(parseSeconds('')).toBeNaN();
  });
});

describe('motion tokens with a document', () => {
  /** Install a document whose custom properties answer from `values`. */
  const fakeDom = (values: Record<string, string>) => {
    const calls: string[] = [];
    Object.defineProperty(globalThis, 'document', { value: { documentElement: {} }, configurable: true });
    Object.defineProperty(globalThis, 'getComputedStyle', {
      value: () => ({
        getPropertyValue: (property: string) => {
          calls.push(property);
          return values[property] ?? '';
        },
      }),
      configurable: true,
    });
    return calls;
  };

  it('reads the active look\'s tempo and ease', () => {
    fakeDom({ '--dur-base': '320ms', '--gsap-ease-emphasized': 'back.out(1.4)' });
    expect(DUR.base).toBeCloseTo(0.32);
    expect(EASE.emphasized).toBe('back.out(1.4)');
  });

  it('falls back per token when the stylesheet has no answer or an unparsable one', () => {
    fakeDom({ '--dur-fast': 'quick' });
    expect(DUR.fast).toBe(FALLBACK_DUR.fast);
    expect(DUR.slow).toBe(FALLBACK_DUR.slow);
    expect(EASE.exit).toBe(FALLBACK_EASE.exit);
  });

  it('asks the stylesheet once per token until the cache is reset', () => {
    const calls = fakeDom({ '--dur-base': '400ms' });
    expect(DUR.base).toBeCloseTo(0.4);
    expect(DUR.base).toBeCloseTo(0.4);
    expect(calls).toEqual(['--dur-base']);
    resetMotionTokenCache();
    const again = fakeDom({ '--dur-base': '120ms' });
    expect(DUR.base).toBeCloseTo(0.12);
    expect(again).toEqual(['--dur-base']);
  });

  it('never throws when getComputedStyle does', () => {
    Object.defineProperty(globalThis, 'document', { value: { documentElement: {} }, configurable: true });
    Object.defineProperty(globalThis, 'getComputedStyle', {
      value: () => {
        throw new Error('detached');
      },
      configurable: true,
    });
    expect(DUR.base).toBe(FALLBACK_DUR.base);
  });
});
