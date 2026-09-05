// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';

import { gsap, motionEnabled } from './gsap';
import { REDUCED_MOTION_QUERY, prefersReducedMotion } from './reducedMotion';
import { DUR, EASE } from './tokens';

/**
 * The motion kill switch.
 *
 * Everything in `src/motion/` asks `motionEnabled()` before it tweens, so this
 * is the one function that decides whether the app animates at all. It has to
 * say no in four separate situations, and a bug in any one of them is invisible
 * in a browser that happens to satisfy the other three — hence one test per
 * reason, plus the "yes" case, which is what stops the guards from being
 * vacuously true.
 */

/** The stub `src/test/setup.ts` installs; every test puts it back. */
const originalMatchMedia = window.matchMedia;

/** Replace `window.matchMedia` (or remove it, with `undefined`). */
function setMatchMedia(implementation: unknown): void {
  Object.defineProperty(window, 'matchMedia', {
    value: implementation,
    writable: true,
    configurable: true,
  });
}

/** A `matchMedia` that answers `matches` and records the queries it was asked. */
function matchMediaStub(matches: boolean): { impl: unknown; queries: string[] } {
  const queries: string[] = [];
  return {
    queries,
    impl: (media: string) => {
      queries.push(media);
      return { matches, media };
    },
  };
}

/**
 * Leave the VITEST short circuit behind so the other guards can be reached.
 * `vi.unstubAllEnvs()` in `afterEach` restores it.
 */
function outsideVitest(): void {
  vi.stubEnv('VITEST', '');
}

afterEach(() => {
  vi.unstubAllEnvs();
  setMatchMedia(originalMatchMedia);
  delete window.__BW_MOTION_OFF__;
});

describe('motionEnabled', () => {
  it('is false under Vitest, whatever the environment says', () => {
    setMatchMedia(matchMediaStub(false).impl);
    expect(motionEnabled()).toBe(false);
  });

  it('is false when the host has no matchMedia at all', () => {
    outsideVitest();
    setMatchMedia(undefined);
    expect(motionEnabled()).toBe(false);
  });

  it('is false when the user prefers reduced motion', () => {
    outsideVitest();
    const stub = matchMediaStub(true);
    setMatchMedia(stub.impl);
    expect(motionEnabled()).toBe(false);
    expect(stub.queries).toContain(REDUCED_MOTION_QUERY);
  });

  it('is false when __BW_MOTION_OFF__ is set', () => {
    outsideVitest();
    setMatchMedia(matchMediaStub(false).impl);
    window.__BW_MOTION_OFF__ = true;
    expect(motionEnabled()).toBe(false);
  });

  it('is true only when every guard passes', () => {
    outsideVitest();
    setMatchMedia(matchMediaStub(false).impl);
    expect(motionEnabled()).toBe(true);
  });
});

describe('prefersReducedMotion', () => {
  it('assumes reduced motion when matchMedia is missing', () => {
    setMatchMedia(undefined);
    expect(prefersReducedMotion()).toBe(true);
  });

  it('is true when the reduce query matches', () => {
    setMatchMedia(matchMediaStub(true).impl);
    expect(prefersReducedMotion()).toBe(true);
  });

  it('is false when the reduce query does not match', () => {
    setMatchMedia(matchMediaStub(false).impl);
    expect(prefersReducedMotion()).toBe(false);
  });
});

describe('the shared gsap instance', () => {
  it('publishes itself on window, which is what makes the e2e guard real', () => {
    // `e2e/fixtures/motion.ts` (frozen) reads `window.gsap.globalTimeline`. The
    // ESM build sets no global, so without this the guard passes on any page.
    expect(window.gsap).toBe(gsap);
  });

  it('carries the token duration and ease as its defaults', () => {
    const defaults = gsap.defaults();
    expect(defaults.duration).toBe(DUR.base);
    expect(defaults.ease).toBe(gsap.parseEase(EASE.standard));
  });
});
