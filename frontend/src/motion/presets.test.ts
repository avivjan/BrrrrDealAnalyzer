// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MODAL_PANEL_SELECTOR, presets, transitionHooks, type MotionPreset } from './presets';
import { CLEAR_PROPS, gsap } from './gsap';

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
  // The real-timeline suites below leave live tweens behind on purpose.
  gsap.globalTimeline.clear();
  document.body.innerHTML = '';
});

/** Jump every live tween to its end, firing `onComplete` (and so `clearProps`). */
function finishEveryTween(): void {
  for (const child of gsap.globalTimeline.getChildren()) child.progress(1);
}

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
    expect(setSpy).toHaveBeenCalledWith(el, { clearProps: CLEAR_PROPS });
    expect(order).toEqual(['killTweensOf', 'set']);
  });

  it.each(leavingPresets)('%s leaveCancelled kills the tween and clears the props', (_name, preset) => {
    const el = document.createElement('div');
    const setSpy = vi.spyOn(gsap, 'set').mockImplementation((() => undefined) as never);
    const killSpy = vi.spyOn(gsap, 'killTweensOf').mockImplementation((() => undefined) as never);

    preset.leaveCancelled!(el);

    expect(killSpy).toHaveBeenCalledWith(el);
    expect(setSpy).toHaveBeenCalledWith(el, { clearProps: CLEAR_PROPS });
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
    // The literal, not `DUR.fast`: the Phase 4 constraint is 150 ms, so a token
    // that drifted upwards has to fail here rather than move the bound with it.
    for (const call of to.mock.calls) {
      expect((call[1] as Vars).duration as number).toBeLessThanOrEqual(0.15);
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

  it('refuses a preset that can leave but cannot be interrupted', () => {
    const halfWritten: MotionPreset = {
      enter: presets.fade.enter,
      enterCancelled: presets.fade.enterCancelled,
      leave: (_el, done) => done(),
    };
    // Loud, not lenient: silently dropping the leave would ship a modal that
    // never animates out and give no clue why.
    expect(() => transitionHooks(halfWritten)).toThrow(/leaveCancelled/);
  });
});

describe('the inline styles the app itself owns', () => {
  /** A CSS custom property and a width, of the kind a template or script sets. */
  const APP_STYLE = '--steps: 7; width: 42px';

  function styled(): HTMLElement {
    const el = document.createElement('div');
    el.setAttribute('style', APP_STYLE);
    document.body.append(el);
    return el;
  }

  function survives(el: HTMLElement): void {
    expect(el.style.getPropertyValue('--steps').trim()).toBe('7');
    expect(el.style.width).toBe('42px');
  }

  it.each(allPresets)('%s enter keeps them on the reduced-motion path', (_name, preset) => {
    const el = styled();
    preset.enter(el, vi.fn());
    survives(el);
  });

  it.each(allPresets)('%s enter keeps them once the tween completes', (_name, preset) => {
    state.motionOn = true;
    const el = styled();
    preset.enter(el, vi.fn());
    finishEveryTween();
    survives(el);
    expect(el.style.opacity).toBe('');
  });

  it.each(allPresets)('%s enterCancelled keeps them', (_name, preset) => {
    state.motionOn = true;
    const el = styled();
    preset.enter(el, vi.fn());
    preset.enterCancelled(el);
    survives(el);
    expect(el.style.opacity).toBe('');
  });

  it.each(leavingPresets)('%s leaveCancelled keeps them and lets the element be clicked again', (_name, preset) => {
    state.motionOn = true;
    const el = styled();
    preset.leave!(el, vi.fn());
    expect(el.style.pointerEvents).toBe('none');

    preset.leaveCancelled!(el);

    expect(el.style.pointerEvents).toBe('');
    survives(el);
  });
});

describe('cancelling, against the real timeline', () => {
  it('modal leaves nothing tweening — the panel included', () => {
    state.motionOn = true;
    const overlay = document.createElement('div');
    const panel = document.createElement('div');
    panel.setAttribute('data-ui', 'modal-panel');
    overlay.append(panel);
    document.body.append(overlay);

    presets.modal.enter(overlay, vi.fn());
    expect(gsap.globalTimeline.getChildren().length).toBeGreaterThanOrEqual(2);

    presets.modal.enterCancelled(overlay);

    expect(gsap.globalTimeline.getChildren()).toHaveLength(0);
    expect(overlay.getAttribute('style') ?? '').toBe('');
    expect(panel.getAttribute('style') ?? '').toBe('');
  });

  it('leaves nothing tweening when a close is interrupted', () => {
    state.motionOn = true;
    const overlay = document.createElement('div');
    const panel = document.createElement('div');
    panel.setAttribute('data-ui', 'modal-panel');
    overlay.append(panel);
    document.body.append(overlay);

    presets.modal.leave!(overlay, vi.fn());
    expect(gsap.globalTimeline.getChildren().length).toBeGreaterThanOrEqual(2);

    presets.modal.leaveCancelled!(overlay);

    expect(gsap.globalTimeline.getChildren()).toHaveLength(0);
    expect(overlay.style.pointerEvents).toBe('');
    expect(panel.getAttribute('style') ?? '').toBe('');
  });
});

describe('every enter, on an element a previous leave made inert', () => {
  /**
   * A completed leave is the one thing `clearProps` does not undo.
   *
   * `pointer-events: none` is written by `leave` and deliberately left out of
   * `CLEAR_PROPS`, so a leave that ran to completion leaves it behind. Vue then
   * reuses that very element for the next open — a modal is one `v-if` node, not
   * a new one per open — and without this reset the reopened dialog would render
   * perfectly and swallow every click.
   *
   * Both paths are checked, because reduced motion is the common one: with
   * motion off the enter never reaches a tween at all.
   */
  it.each(allPresets)('%s enter clears pointer-events (motion off)', (_name, preset) => {
    const el = document.createElement('div');
    el.style.pointerEvents = 'none';

    preset.enter(el, vi.fn());

    expect(el.style.pointerEvents).toBe('');
  });

  it.each(allPresets)('%s enter clears pointer-events (motion on)', (_name, preset) => {
    state.motionOn = true;
    const el = document.createElement('div');
    document.body.append(el);
    el.style.pointerEvents = 'none';

    preset.enter(el, vi.fn());

    expect(el.style.pointerEvents).toBe('');
  });

  it.each(allPresets)('%s enter clears pointer-events before it tweens', (_name, preset) => {
    state.motionOn = true;
    const order: string[] = [];
    const el = trackedElement(order);
    el.style.pointerEvents = 'none';
    order.length = 0;
    spyOnGsap(order);

    preset.enter(el, vi.fn());

    expect(order[0]).toBe('pointer-events:');
  });

  it('a modal that finished leaving is clickable again once it re-enters', () => {
    state.motionOn = true;
    const overlay = document.createElement('div');
    const panel = document.createElement('div');
    panel.setAttribute('data-ui', 'modal-panel');
    overlay.append(panel);
    document.body.append(overlay);

    presets.modal.leave!(overlay, vi.fn());
    finishEveryTween();
    expect(overlay.style.pointerEvents).toBe('none');

    // Vue reuses the same node for the next open.
    presets.modal.enter(overlay, vi.fn());
    finishEveryTween();

    expect(overlay.style.pointerEvents).toBe('');
    expect(overlay.getAttribute('style') ?? '').toBe('');
  });
});
