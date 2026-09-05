/**
 * The one global the motion layer reads.
 *
 * `__BW_MOTION_OFF__` is an escape hatch for anything that needs a still page
 * without changing the user's OS setting: a screenshot run, a debugging
 * session, a future "reduce animation" preference. Nothing in the app sets it;
 * `motionEnabled()` only ever reads it, so an undefined value is the norm.
 *
 * `export {}` makes this file a module, so `declare global` augments the real
 * `Window` instead of declaring a fresh one that would replace it.
 */
export {};

declare global {
  interface Window {
    /** When truthy, every preset and directive in `src/motion/` is inert. */
    __BW_MOTION_OFF__?: boolean;
  }
}
