// @vitest-environment node
/// <reference types="node" />
// The `node` environment on purpose: `registerMotion` needs no DOM, and only
// under `node` is `import.meta.url` a `file:` URL the read below can resolve.
// `tsconfig.app.json` scopes `types` to `vite/client`, so the Node import needs
// its types spelled out.
import { readFileSync } from 'node:fs';
import { describe, expect, it, vi } from 'vitest';
import type { App } from 'vue';

import { registerMotion } from './index';
import UiTransition from './UiTransition.vue';
import UiTransitionGroup from './UiTransitionGroup.vue';
import { vCountUp, vFlash, vHoverLift, vPress, vReveal } from './directives';

/**
 * Global registration.
 *
 * A view template may write `<UiTransition>` or `v-press` with no import,
 * because `main.ts` calls this once on the app. The names are therefore the
 * public contract: rename one here and every template using it silently falls
 * back to an unknown element or an ignored attribute.
 */

/** The smallest thing `registerMotion` needs. */
function fakeApp(): App {
  return { component: vi.fn(), directive: vi.fn() } as unknown as App;
}

describe('registerMotion', () => {
  it('registers both wrapper components under their template names', () => {
    const app = fakeApp();
    registerMotion(app);
    expect(app.component).toHaveBeenCalledWith('UiTransition', UiTransition);
    expect(app.component).toHaveBeenCalledWith('UiTransitionGroup', UiTransitionGroup);
    expect(app.component).toHaveBeenCalledTimes(2);
  });

  it('registers the five directives under their kebab-case names', () => {
    const app = fakeApp();
    registerMotion(app);
    expect(app.directive).toHaveBeenCalledWith('reveal', vReveal);
    expect(app.directive).toHaveBeenCalledWith('press', vPress);
    expect(app.directive).toHaveBeenCalledWith('hover-lift', vHoverLift);
    expect(app.directive).toHaveBeenCalledWith('flash', vFlash);
    expect(app.directive).toHaveBeenCalledWith('count-up', vCountUp);
    expect(app.directive).toHaveBeenCalledTimes(5);
  });
});

describe('the ambient typing', () => {
  const declarations = readFileSync(new URL('../components.d.ts', import.meta.url), 'utf8');

  it.each(['UiTransition', 'UiTransitionGroup'])(
    'declares %s on GlobalComponents, so vue-tsc checks its props',
    (name) => {
      expect(declarations).toContain(`${name}: typeof import("./motion/${name}.vue")`);
    },
  );
});
