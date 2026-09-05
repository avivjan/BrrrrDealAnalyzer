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
 * Importing this module has two side effects and no others: `gsap.defaults`,
 * and publishing the instance on `window` for the e2e guard.
 */
import { gsap } from 'gsap';

import { prefersReducedMotion } from './reducedMotion';
import { DUR, EASE } from './tokens';

gsap.defaults({ duration: DUR.base, ease: EASE.standard });

/**
 * Publish the instance for the e2e motion guard.
 *
 * `e2e/fixtures/motion.ts` (frozen since Phase 0) asserts that nothing is still
 * tweening once an interaction settles, by reading
 * `window.gsap.globalTimeline.getChildren()`. The ESM build sets no global, so
 * without this the guard would pass on any page whatever was animating.
 */
if (typeof window !== 'undefined') window.gsap = gsap;

export { gsap };

/**
 * The properties this layer owns, and the only ones it ever removes.
 *
 * Every enter hands these back to the stylesheet through `clearProps` when it
 * completes, and every cancel and unmount removes exactly these. Deliberately
 * *not* `clearProps: 'all'`, which wipes the element's entire inline `style`
 * attribute — including whatever the app itself put there (`:style="…"`, a
 * width a script measured, a CSS custom property a template set). Under reduced
 * motion the disabled path runs on every single enter, so a broad wipe would be
 * destructive for most users rather than for none.
 */
export const CLEAR_PROPS = 'transform,opacity,filter,willChange';

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
