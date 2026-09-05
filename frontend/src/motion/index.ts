/**
 * The motion layer's single entry point.
 *
 * `main.ts` calls `registerMotion(app)` once, which is what lets a frozen view
 * template write `<UiTransition preset="modal">` or `v-press` with no import
 * and no script change. The names below are therefore a public contract:
 * `src/components.d.ts` mirrors the two components into `vue`'s
 * `GlobalComponents` so `vue-tsc` checks their props, and `src/test/setup.ts`
 * installs pass-through stubs under the same names so a mounted view resolves
 * them in Vitest too.
 *
 * Re-exported here so a later phase can import the pieces directly if it ever
 * needs to (`src/motion` is on the G3 allow-list of importable modules).
 */
import type { App } from 'vue';

import UiTransition from './UiTransition.vue';
import UiTransitionGroup from './UiTransitionGroup.vue';
import { vCountUp, vFlash, vHoverLift, vPress, vReveal } from './directives';

export { gsap, motionEnabled } from './gsap';
export { prefersReducedMotion, REDUCED_MOTION_QUERY } from './reducedMotion';
export { presets, transitionHooks, type MotionPreset, type PresetName } from './presets';
export { vCountUp, vFlash, vHoverLift, vPress, vReveal };
export { DUR, EASE } from './tokens';
export { UiTransition, UiTransitionGroup };

/** Register the wrappers and the directives, so templates need no import. */
export function registerMotion(app: App): void {
  app.component('UiTransition', UiTransition);
  app.component('UiTransitionGroup', UiTransitionGroup);
  app.directive('reveal', vReveal);
  app.directive('press', vPress);
  app.directive('hover-lift', vHoverLift);
  app.directive('flash', vFlash);
  app.directive('count-up', vCountUp);
}
