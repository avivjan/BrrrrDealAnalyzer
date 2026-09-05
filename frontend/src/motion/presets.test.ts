// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MODAL_PANEL_SELECTOR, presets, transitionHooks } from './presets';
import { gsap } from './gsap';
import { DUR } from './tokens';

/**
 * The `<Transition>` hook implementations.
 *
 * Two situations matter and they are opposites, so both are exercised here:
 *
 *  - Motion off (the default: `motionEnabled()` is false under Vitest). Vue is
 *    waiting on `done`; a preset that forgot to call it would leave the element
 *    stuck in the DOM forever, which is why every preset is checked rather than
 *    a representative one.
 *  - Motion on (`motionEnabled` mocked true, `gsap.fromTo` / `gsap.to` stubbed
 *    so nothing actually animates). Then the assertions are about the *vars*:
 *    what a preset asks GSAP to touch, and what it promises to clean up after.
 */

/** Flipped per test; read by the mocked `motionEnabled` below. */
const state = vi.hoisted(() => ({ motionOn: false }));

vi.mock('./gsap', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./gsap')>();
  // Same `gsap` object the presets hold, so `vi.spyOn(gsap, …)` reaches them.
  return { ...actual, motionEnabled: () => state.motionOn };
});

type Vars = Record<string, unknown>;

/** Every preset, as `[name, preset]` pairs. */
const allPresets = Object.entries(presets);

/** The presets that animate on the way out. */
const leavingPresets = allPresets.filter(([, preset]) => typeof preset.leave === 'function');

/**
 * An element whose `pointer-events` writes are recorded in `order` alongside
 * the GSAP calls, so "pointer-events first" can be asserted as an ordering
 * rather than merely as an end state.
 */
function trackedElement(order: string[]): HTMLElement {
  const el = document.createElement('div');
  let stored = '';
  Object.defineProperty(el.style, 'pointerEvents', {
    configurable: true,
    get: () => stored,
    set: (value: string) => {
      stored = value;
      order.push(`pointer-events:${value}`);
    },
  });
  return el;
}

/** Record every GSAP entry point the presets use, in call order. */
function spyOnGsap(order: string[]): {
  fromTo: ReturnType<typeof vi.fn>;
  to: ReturnType<typeof vi.fn>;
} {
  const fromTo = vi.fn();
  const to = vi.fn();
  vi.spyOn(gsap, 'killTweensOf').mockImplementation(((...args: unknown[]) => {
    order.push('killTweensOf');
    return args as never;
  }) as never);
  vi.spyOn(gsap, 'set').mockImplementation(((...args: unknown[]) => {
    order.push('set');
    return args as never;
  }) as never);
  vi.spyOn(gsap, 'fromTo').mockImplementation(((...args: unknown[]) => {
    order.push('fromTo');
    fromTo(...args);
    return args as never;
  }) as never);
  vi.spyOn(gsap, 'to').mockImplementation(((...args: unknown[]) => {
    order.push('to');
    to(...args);
    return args as never;
  }) as never);
  return { fromTo, to };
}

beforeEach(() => {
  state.motionOn = false;
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('every preset, with motion off', () => {
  it.each(allPresets)('%s enter calls done synchronously and leaves no inline style', (_name, preset) => {
    const el = document.createElement('div');
    const done = vi.fn();
    preset.enter(el, done);
    expect(done).toHaveBeenCalledTimes(1);
    expect(el.getAttribute('style') ?? '').toBe('');
  });

  it.each(allPresets)('%s enter clears inline styles a previous tween left behind', (_name, preset) => {
    const el = document.createElement('div');
    el.style.opacity = '0';
    el.style.transform = 'translateY(8px)';
    preset.enter(el, vi.fn());
    expect(el.getAttribute('style') ?? '').toBe('');
  });

  it.each(leavingPresets)('%s leave calls done synchronously', (_name, preset) => {
    const el = document.createElement('div');
    const done = vi.fn();
    preset.leave!(el, done);
    expect(done).toHaveBeenCalledTimes(1);
  });
});

describe('every leave, whatever the motion setting', () => {
  it.each(leavingPresets)('%s makes the element inert before anything else (motion off)', (_name, preset) => {
    const order: string[] = [];
    const el = trackedElement(order);
    spyOnGsap(order);
    preset.leave!(el, vi.fn());
    expect(order[0]).toBe('pointer-events:none');
  });

  it.each(leavingPresets)('%s makes the element inert before anything else (motion on)', (_name, preset) => {
    state.motionOn = true;
    const order: string[] = [];
    const el = trackedElement(order);
    spyOnGsap(order);
    preset.leave!(el, vi.fn());
    expect(order[0]).toBe('pointer-events:none');
    expect(order).toContain('to');
  });

  it.each(leavingPresets)('%s hands done to GSAP rather than dropping it (motion on)', (_name, preset) => {
    state.motionOn = true;
    const order: string[] = [];
    const el = trackedElement(order);
    const { to } = spyOnGsap(order);
    const done = vi.fn();
    preset.leave!(el, done);
    const vars = to.mock.calls[0]?.[1] as Vars;
    expect(vars.onComplete).toBe(done);
    expect(done).not.toHaveBeenCalled();
  });
});

describe('the page preset', () => {
  it('touches opacity and nothing else', () => {
    state.motionOn = true;
    const { fromTo } = spyOnGsap([]);
    presets.page.enter(document.createElement('div'), vi.fn());

    const [, from, to] = fromTo.mock.calls[0] as [unknown, Vars, Vars];
    for (const vars of [from, to]) {
      for (const forbidden of ['x', 'y', 'z', 'scale', 'scaleX', 'scaleY', 'rotation', 'transform']) {
        expect(vars, forbidden).not.toHaveProperty(forbidden);
      }
    }
    expect(from).toHaveProperty('opacity', 0);
    expect(to).toHaveProperty('opacity', 1);
  });

  it('has no leave at all, so Vue removes the old page immediately', () => {
    expect(presets.page.leave).toBeUndefined();
  });
});

describe('every enter, with motion on', () => {
  it.each(allPresets)('%s promises to clear the properties it tweened', (_name, preset) => {
    state.motionOn = true;
    const { fromTo } = spyOnGsap([]);
    preset.enter(document.createElement('div'), vi.fn());

    expect(fromTo).toHaveBeenCalled();
    for (const call of fromTo.mock.calls) {
      const to = call[2] as Vars;
      expect(to.clearProps, String(to.clearProps)).toEqual(expect.any(String));
      expect(to.overwrite).toBe('auto');
    }
  });

  it.each(allPresets)('%s ends by calling done', (_name, preset) => {
    state.motionOn = true;
    const { fromTo } = spyOnGsap([]);
    const done = vi.fn();
    preset.enter(document.createElement('div'), done);
    const completions = fromTo.mock.calls.filter((call) => (call[2] as Vars).onComplete === done);
    expect(completions).toHaveLength(1);
  });
});

describe('the cancelled hooks', () => {
  it.each(allPresets)('%s enterCancelled kills the tween and clears the props', (_name, preset) => {
    const order: string[] = [];
    const el = document.createElement('div');
    const setSpy = vi.spyOn(gsap, 'set').mockImplementation(((...args: unknown[]) => {
      order.push('set');
      return args as never;
    }) as never);
    const killSpy = vi.spyOn(gsap, 'killTweensOf').mockImplementation(((...args: unknown[]) => {
      order.push('killTweensOf');
      return args as never;
    }) as never);

    preset.enterCancelled(el);

    expect(killSpy).toHaveBeenCalledWith(el);
    expect(setSpy).toHaveBeenCalledWith(el, { clearProps: 'all' });
    expect(order).toEqual(['killTweensOf', 'set']);
  });

  it.each(leavingPresets)('%s leaveCancelled kills the tween and clears the props', (_name, preset) => {
    const el = document.createElement('div');
    const setSpy = vi.spyOn(gsap, 'set').mockImplementation((() => undefined) as never);
    const killSpy = vi.spyOn(gsap, 'killTweensOf').mockImplementation((() => undefined) as never);

    preset.leaveCancelled!(el);

    expect(killSpy).toHaveBeenCalledWith(el);
    expect(setSpy).toHaveBeenCalledWith(el, { clearProps: 'all' });
  });
});

describe('the modal preset', () => {
  it('scales the panel, never the fixed overlay that carries it', () => {
    state.motionOn = true;
    const overlay = document.createElement('div');
    const panel = document.createElement('div');
    panel.setAttribute('data-ui', 'modal-panel');
    overlay.appendChild(panel);
    const { fromTo } = spyOnGsap([]);

    presets.modal.enter(overlay, vi.fn());

    const byTarget = new Map(fromTo.mock.calls.map((call) => [call[0], call as [unknown, Vars, Vars]]));
    const overlayVars = byTarget.get(overlay);
    const panelVars = byTarget.get(panel);
    expect(overlayVars, 'the overlay is tweened').toBeDefined();
    expect(panelVars, 'the panel is tweened').toBeDefined();
    expect(overlayVars![1]).not.toHaveProperty('scale');
    expect(overlayVars![2]).not.toHaveProperty('scale');
    expect(panelVars![1]).toHaveProperty('scale', 0.96);
    expect(panelVars![2]).toHaveProperty('scale', 1);
  });

  it('scales the element itself when the transition already wraps the panel', () => {
    state.motionOn = true;
    const panel = document.createElement('div');
    panel.setAttribute('data-ui', 'modal-panel');
    const { fromTo } = spyOnGsap([]);

    presets.modal.enter(panel, vi.fn());

    expect(fromTo).toHaveBeenCalledTimes(1);
    const [, from, to] = fromTo.mock.calls[0] as [unknown, Vars, Vars];
    expect(from).toMatchObject({ opacity: 0, scale: 0.96 });
    expect(to).toMatchObject({ opacity: 1, scale: 1 });
  });

  it('leaves a plain overlay to fade, with no transform at all', () => {
    state.motionOn = true;
    const overlay = document.createElement('div');
    const { fromTo } = spyOnGsap([]);

    presets.modal.enter(overlay, vi.fn());

    expect(fromTo).toHaveBeenCalledTimes(1);
    const [, from, to] = fromTo.mock.calls[0] as [unknown, Vars, Vars];
    expect(from).not.toHaveProperty('scale');
    expect(to).not.toHaveProperty('scale');
  });

  it('names the selector the panel actually carries', () => {
    expect(MODAL_PANEL_SELECTOR).toBe('[data-ui="modal-panel"]');
  });

  it('opens well inside the 300 ms the analyze debounce leaves it', () => {
    state.motionOn = true;
    const { fromTo } = spyOnGsap([]);
    presets.modal.enter(document.createElement('div'), vi.fn());
    for (const call of fromTo.mock.calls) {
      expect((call[2] as Vars).duration as number).toBeLessThanOrEqual(0.25);
    }
  });

  it('closes in at most 150 ms', () => {
    state.motionOn = true;
    const { to } = spyOnGsap([]);
    presets.modal.leave!(document.createElement('div'), vi.fn());
    for (const call of to.mock.calls) {
      expect((call[1] as Vars).duration as number).toBeLessThanOrEqual(DUR.fast);
    }
  });

  it('has an enter-only twin for the surfaces that must never animate out', () => {
    expect(presets.modalEnterOnly.leave).toBeUndefined();
    expect(presets.fade.leave).toBeUndefined();
    expect(presets.slideUp.leave).toBeUndefined();
  });
});

describe('transitionHooks', () => {
  it('omits the leave hooks entirely for an enter-only preset', () => {
    const hooks = transitionHooks(presets.page);
    expect(Object.keys(hooks).sort()).toEqual(['onEnter', 'onEnterCancelled']);
  });

  it('wires both directions for a preset that animates out', () => {
    const hooks = transitionHooks(presets.modal);
    expect(Object.keys(hooks).sort()).toEqual([
      'onEnter',
      'onEnterCancelled',
      'onLeave',
      'onLeaveCancelled',
    ]);
  });

  it('never offers a mode, so Vue never holds an entering element back', () => {
    for (const preset of Object.values(presets)) {
      expect(transitionHooks(preset)).not.toHaveProperty('mode');
    }
  });
});
