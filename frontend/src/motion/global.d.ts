/**
 * The two globals the motion layer touches.
 *
 * `__BW_MOTION_OFF__` is an escape hatch for anything that needs a still page
 * without changing the user's OS setting: a screenshot run, a debugging
 * session, a future "reduce animation" preference. Nothing in the app sets it;
 * `motionEnabled()` only ever reads it, so an undefined value is the norm.
 *
 * `gsap` is the app's own instance, published by `gsap.ts` so the frozen e2e
 * motion guard (`e2e/fixtures/motion.ts`) can read `gsap.globalTimeline` and
 * assert that nothing is still tweening. The ESM build publishes no global of
 * its own, so without that line the guard would pass on any page.
 *
 * `export {}` makes this file a module, so `declare global` augments the real
 * `Window` instead of declaring a fresh one that would replace it.
 */
export {};

declare global {
  interface Window {
    /** When truthy, every preset and directive in `src/motion/` is inert. */
    __BW_MOTION_OFF__?: boolean;
    /** The app's GSAP instance, published for the e2e motion guard. */
    gsap?: GSAP;
  }
}
