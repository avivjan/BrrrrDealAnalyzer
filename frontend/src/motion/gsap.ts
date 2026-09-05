/**
 * The single GSAP instance, and the switch that decides whether it runs.
 *
 * Everything in `src/motion/` imports `gsap` from here rather than from the
 * package, for two reasons: the token defaults below are applied exactly once,
 * and the presets and directives share one module with `motionEnabled()` so a
 * test can replace the switch with `vi.mock('./gsap')` and still hold the very
 * `gsap` object they tween with.
 *
 * Core only — no `ScrollTrigger`, no `Flip`, no `gsap/all`. The overhaul's
 * motion is entrances, presses and fades; a plugin would cost bundle size for
 * behaviour nothing in the plan asks for.
 *
 * The only side effect of importing this module is `gsap.defaults`.
 */
import { gsap } from 'gsap';

import { prefersReducedMotion } from './reducedMotion';
import { DUR, EASE } from './tokens';

gsap.defaults({ duration: DUR.base, ease: EASE.standard });

export { gsap };

/**
 * Whether the app may animate at all.
 *
 * Four separate "no"s, each of which is the whole answer on its own:
 *
 *  - Under Vitest. Unit tests assert that a `<Transition>` hook calls `done()`
 *    synchronously; a running tween would make that a timing race, and every
 *    component test would pay for a real animation frame it does not need. A
 *    test that wants motion *on* mocks this function.
 *  - Without a `window` — nothing to animate.
 *  - When the user prefers reduced motion (see `reducedMotion.ts`). The
 *    Playwright functional projects run with `reducedMotion: 'reduce'`, so this
 *    is also what keeps the characterization suite deterministic.
 *  - When `window.__BW_MOTION_OFF__` is set, the manual override.
 */
export function motionEnabled(): boolean {
  if (import.meta.env.VITEST) return false;
  if (typeof window === 'undefined') return false;
  if (window.__BW_MOTION_OFF__) return false;
  return !prefersReducedMotion();
}
