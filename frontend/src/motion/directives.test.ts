// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { DirectiveBinding, ObjectDirective } from 'vue';

import { CLEAR_PROPS, gsap } from './gsap';
import { DUR } from './tokens';
import {
  FLASH_DURATION,
  REVEAL_CHILD_SELECTOR,
  vCountUp,
  vFlash,
  vHoverLift,
  vPress,
  vReveal,
} from './directives';

/**
 * The five directives.
 *
 * They are attached to frozen view templates as bare attributes — `v-press`,
 * never `v-press="something"` — because Phase 4 may not add a single line to a
 * view's `<script setup>`, so there is no expression for them to read. Every
 * test therefore hands the hook a binding whose `value`, `oldValue` and `arg`
 * throw on access: reading one is a test failure, not a silent coupling.
 *
 * The other two invariants are about the host page. A directive decorates an
 * element someone else owns, so it must never cancel that element's events (a
 * `v-press` on a `<label>` that called `preventDefault` would stop the click
 * from reaching the input) and must never rewrite that element's text.
 */

/** Flipped per test; read by the mocked `motionEnabled` below. */
const state = vi.hoisted(() => ({ motionOn: false }));

vi.mock('./gsap', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./gsap')>();
  return { ...actual, motionEnabled: () => state.motionOn };
});

type Vars = Record<string, unknown>;
type Directive = ObjectDirective<HTMLElement>;

const originalMatchMedia = window.matchMedia;

/** A binding that fails the test the moment a directive reads an expression. */
function valuelessBinding(modifiers: Record<string, boolean> = {}): DirectiveBinding {
  return {
    get value(): never {
      throw new Error('a motion directive read binding.value');
    },
    get oldValue(): never {
      throw new Error('a motion directive read binding.oldValue');
    },
    get arg(): never {
      throw new Error('a motion directive read binding.arg');
    },
    modifiers,
    instance: null,
    dir: {},
  } as unknown as DirectiveBinding;
}

/** Invoke one directive hook the way Vue would. */
function hook(
  directive: Directive,
  name: 'mounted' | 'updated' | 'unmounted',
  el: HTMLElement,
  modifiers: Record<string, boolean> = {},
): void {
  directive[name]?.(el, valuelessBinding(modifiers), null as never, null as never);
}

/** Answer `(hover: hover)` (and every other query) with `matches`. */
function setHoverSupport(matches: boolean): void {
  Object.defineProperty(window, 'matchMedia', {
    value: (media: string) => ({ matches, media }),
    writable: true,
    configurable: true,
  });
}

/** Swallow every tween so the assertions are about the vars, not the pixels. */
function stubTweens(): { fromTo: ReturnType<typeof vi.fn>; to: ReturnType<typeof vi.fn> } {
  const fromTo = vi.fn();
  const to = vi.fn();
  // The stub returns something killable, because `v-reveal.stagger` keeps the
  // handle its `fromTo` returns and kills it on unmount.
  vi.spyOn(gsap, 'fromTo').mockImplementation(((...args: unknown[]) => {
    fromTo(...args);
    return { kill() {} } as never;
  }) as never);
  vi.spyOn(gsap, 'to').mockImplementation(((...args: unknown[]) => {
    to(...args);
    return { kill() {} } as never;
  }) as never);
  return { fromTo, to };
}

/** An element with `count` `[data-reveal]` children. */
function withRevealChildren(count: number): HTMLElement {
  const el = document.createElement('div');
  for (let index = 0; index < count; index += 1) {
    const child = document.createElement('p');
    child.setAttribute('data-reveal', '');
    el.append(child);
  }
  return el;
}

const allDirectives: [string, Directive][] = [
  ['v-reveal', vReveal],
  ['v-press', vPress],
  ['v-hover-lift', vHoverLift],
  ['v-flash', vFlash],
  ['v-count-up', vCountUp],
];

beforeEach(() => {
  state.motionOn = false;
  setHoverSupport(true);
});

afterEach(() => {
  vi.restoreAllMocks();
  // The real-timeline suite below leaves live tweens behind on purpose.
  gsap.globalTimeline.clear();
  Object.defineProperty(window, 'matchMedia', {
    value: originalMatchMedia,
    writable: true,
    configurable: true,
  });
  document.body.innerHTML = '';
});

describe('every directive', () => {
  it.each(allDirectives)('%s reads no expression from its binding', (_name, directive) => {
    state.motionOn = true;
    stubTweens();
    const el = withRevealChildren(2);
    el.textContent = '1';
    document.body.append(el);

    expect(() => {
      hook(directive, 'mounted', el, { stagger: true });
      el.textContent = '2';
      hook(directive, 'updated', el, { stagger: true });
      hook(directive, 'unmounted', el, { stagger: true });
    }).not.toThrow();
  });

  it.each(allDirectives)('%s does nothing at all when motion is off', (_name, directive) => {
    const { fromTo, to } = stubTweens();
    const el = withRevealChildren(2);
    el.textContent = '1,000';
    document.body.append(el);
    const addEventListener = vi.spyOn(el, 'addEventListener');

    hook(directive, 'mounted', el, { stagger: true });
    el.textContent = '2,000';
    hook(directive, 'updated', el, { stagger: true });

    expect(fromTo).not.toHaveBeenCalled();
    expect(to).not.toHaveBeenCalled();
    expect(addEventListener).not.toHaveBeenCalled();
    expect(el.textContent).toBe('2,000');
  });

  it.each(allDirectives)('%s clears up after itself on unmount', (_name, directive) => {
    state.motionOn = true;
    stubTweens();
    const kill = vi.spyOn(gsap, 'killTweensOf').mockImplementation((() => undefined) as never);
    const set = vi.spyOn(gsap, 'set').mockImplementation((() => undefined) as never);
    const el = document.createElement('div');
    document.body.append(el);

    hook(directive, 'mounted', el);
    hook(directive, 'unmounted', el);

    expect(kill).toHaveBeenCalledWith(el);
    expect(set).toHaveBeenCalledWith(el, { clearProps: CLEAR_PROPS });
  });

  it.each(allDirectives)('%s keeps the inline styles the app itself set', (_name, directive) => {
    state.motionOn = true;
    const el = withRevealChildren(2);
    el.setAttribute('style', '--steps: 7; width: 42px');
    document.body.append(el);

    hook(directive, 'mounted', el, { stagger: true });
    hook(directive, 'unmounted', el, { stagger: true });

    expect(el.style.getPropertyValue('--steps').trim()).toBe('7');
    expect(el.style.width).toBe('42px');
  });
});

describe('unmounting, against the real timeline', () => {
  it('v-reveal.stagger leaves nothing tweening on the children it animated', () => {
    state.motionOn = true;
    const el = withRevealChildren(3);
    document.body.append(el);

    hook(vReveal, 'mounted', el, { stagger: true });
    expect(gsap.globalTimeline.getChildren().length).toBeGreaterThanOrEqual(1);

    hook(vReveal, 'unmounted', el, { stagger: true });

    expect(gsap.globalTimeline.getChildren()).toHaveLength(0);
    for (const child of Array.from(el.children)) {
      expect(child.getAttribute('style') ?? '').toBe('');
    }
  });

  it('lets a batch already in flight finish when a second one arrives', () => {
    state.motionOn = true;
    const el = withRevealChildren(2);
    document.body.append(el);
    hook(vReveal, 'mounted', el, { stagger: true });

    const late = document.createElement('p');
    late.setAttribute('data-reveal', '');
    el.append(late);
    hook(vReveal, 'updated', el, { stagger: true });

    // Two live batches, not one: killing the first to make room for the second
    // would strand its children half-faded, with no onComplete left to clear.
    expect(gsap.globalTimeline.getChildren()).toHaveLength(2);

    hook(vReveal, 'unmounted', el, { stagger: true });

    expect(gsap.globalTimeline.getChildren()).toHaveLength(0);
    for (const child of Array.from(el.children)) {
      expect(child.getAttribute('style') ?? '').toBe('');
    }
  });
});

describe('the pointer directives', () => {
  const pointerEvents = [
    ['v-press', vPress, ['pointerdown', 'pointerup', 'pointercancel', 'pointerleave']],
    ['v-hover-lift', vHoverLift, ['pointerenter', 'pointerleave']],
  ] as const;

  it.each(pointerEvents)('%s never cancels or swallows the event', (_name, directive, events) => {
    state.motionOn = true;
    stubTweens();
    const el = document.createElement('button');
    document.body.append(el);
    hook(directive, 'mounted', el);

    for (const type of events) {
      const event = new Event(type, { bubbles: true, cancelable: true });
      const preventDefault = vi.spyOn(event, 'preventDefault');
      const stopPropagation = vi.spyOn(event, 'stopPropagation');
      el.dispatchEvent(event);
      expect(preventDefault, type).not.toHaveBeenCalled();
      expect(stopPropagation, type).not.toHaveBeenCalled();
      expect(event.defaultPrevented, type).toBe(false);
    }
  });

  it.each(pointerEvents)('%s listens passively', (_name, directive, _events) => {
    state.motionOn = true;
    stubTweens();
    const el = document.createElement('button');
    document.body.append(el);
    const addEventListener = vi.spyOn(el, 'addEventListener');

    hook(directive, 'mounted', el);

    expect(addEventListener).toHaveBeenCalled();
    for (const call of addEventListener.mock.calls) {
      expect(call[2], String(call[0])).toEqual({ passive: true });
    }
  });

  it.each(pointerEvents)('%s stops listening once unmounted', (_name, directive, events) => {
    state.motionOn = true;
    const { to } = stubTweens();
    const el = document.createElement('button');
    document.body.append(el);

    hook(directive, 'mounted', el);
    hook(directive, 'unmounted', el);
    to.mockClear();
    for (const type of events) el.dispatchEvent(new Event(type, { bubbles: true }));

    expect(to).not.toHaveBeenCalled();
  });
});

describe('v-press', () => {
  it('presses the element in and releases it again', () => {
    state.motionOn = true;
    const { to } = stubTweens();
    const el = document.createElement('button');
    document.body.append(el);
    hook(vPress, 'mounted', el);

    el.dispatchEvent(new Event('pointerdown'));
    expect((to.mock.calls[0]?.[1] as Vars).scale).toBe(0.97);

    el.dispatchEvent(new Event('pointerup'));
    expect((to.mock.calls[1]?.[1] as Vars).scale).toBe(1);
  });
});

describe('v-hover-lift', () => {
  it('lifts by two pixels and puts the element back', () => {
    state.motionOn = true;
    const { to } = stubTweens();
    const el = document.createElement('div');
    document.body.append(el);
    hook(vHoverLift, 'mounted', el);

    el.dispatchEvent(new Event('pointerenter'));
    expect((to.mock.calls[0]?.[1] as Vars).y).toBe(-2);

    el.dispatchEvent(new Event('pointerleave'));
    expect((to.mock.calls[1]?.[1] as Vars).y).toBe(0);
  });

  it('stays out of the way on a device with no hover', () => {
    state.motionOn = true;
    stubTweens();
    setHoverSupport(false);
    const el = document.createElement('div');
    document.body.append(el);
    const addEventListener = vi.spyOn(el, 'addEventListener');

    hook(vHoverLift, 'mounted', el);

    expect(addEventListener).not.toHaveBeenCalled();
  });
});

describe('v-reveal', () => {
  it('reveals the element itself when it carries no stagger modifier', () => {
    state.motionOn = true;
    const { fromTo } = stubTweens();
    const el = withRevealChildren(3);
    document.body.append(el);

    hook(vReveal, 'mounted', el);

    expect(fromTo).toHaveBeenCalledTimes(1);
    expect(fromTo.mock.calls[0]?.[0]).toBe(el);
  });

  it('staggers the marked children instead when it does', () => {
    state.motionOn = true;
    const { fromTo } = stubTweens();
    const el = withRevealChildren(3);
    document.body.append(el);

    hook(vReveal, 'mounted', el, { stagger: true });

    expect(fromTo).toHaveBeenCalledTimes(1);
    const [targets, , to] = fromTo.mock.calls[0] as [HTMLElement[], Vars, Vars];
    expect(targets).toHaveLength(3);
    expect(targets[0]).toBe(el.children[0]);
    expect(to.stagger).toEqual({ each: 0.06 });
    expect(to.ease).toBe('back.out(1.4)');
    expect(to.duration).toBe(DUR.slow);
  });

  it('animates only the children that arrived since the last render', () => {
    state.motionOn = true;
    const { fromTo } = stubTweens();
    const el = withRevealChildren(2);
    document.body.append(el);
    hook(vReveal, 'mounted', el, { stagger: true });
    fromTo.mockClear();

    const late = document.createElement('p');
    late.setAttribute('data-reveal', '');
    el.append(late);
    hook(vReveal, 'updated', el, { stagger: true });

    const [targets] = fromTo.mock.calls[0] as [HTMLElement[]];
    expect(targets).toEqual([late]);
  });

  it('does nothing on an update that added no children', () => {
    state.motionOn = true;
    const { fromTo } = stubTweens();
    const el = withRevealChildren(2);
    document.body.append(el);
    hook(vReveal, 'mounted', el, { stagger: true });
    fromTo.mockClear();

    hook(vReveal, 'updated', el, { stagger: true });

    expect(fromTo).not.toHaveBeenCalled();
  });

  it('names the attribute a staggered child must carry', () => {
    expect(REVEAL_CHILD_SELECTOR).toBe('[data-reveal]');
  });
});

describe('v-flash', () => {
  it('tints the background when the text changes, without touching the text', () => {
    state.motionOn = true;
    const { fromTo } = stubTweens();
    const el = document.createElement('span');
    el.textContent = '$1,000';
    document.body.append(el);
    hook(vFlash, 'mounted', el);

    el.textContent = '$2,000';
    hook(vFlash, 'updated', el);

    expect(el.textContent).toBe('$2,000');
    const [target, from, to] = fromTo.mock.calls[0] as [HTMLElement, Vars, Vars];
    expect(target).toBe(el);
    expect(from).toHaveProperty('backgroundColor');
    expect(to).toHaveProperty('backgroundColor');
    expect(to.duration).toBe(FLASH_DURATION);
    expect(FLASH_DURATION).toBe(0.4);
  });

  it('stays quiet when the text is the same as last render', () => {
    state.motionOn = true;
    const { fromTo } = stubTweens();
    const el = document.createElement('span');
    el.textContent = '$1,000';
    document.body.append(el);
    hook(vFlash, 'mounted', el);

    hook(vFlash, 'updated', el);

    expect(fromTo).not.toHaveBeenCalled();
  });
});

describe('v-count-up', () => {
  /** Run the whole count in one synchronous go, recording the text at each step. */
  function runCount(el: HTMLElement, frames: string[]): void {
    vi.spyOn(gsap, 'to').mockImplementation(((target: unknown, vars: unknown) => {
      const counter = target as { value: number };
      const options = vars as { value: number; onUpdate?: () => void; onComplete?: () => void };
      options.onUpdate?.();
      frames.push(el.textContent ?? '');
      counter.value = options.value;
      options.onUpdate?.();
      frames.push(el.textContent ?? '');
      options.onComplete?.();
      frames.push(el.textContent ?? '');
      return undefined as never;
    }) as never);
  }

  it('counts from the old number and lands on the exact string Vue rendered', () => {
    state.motionOn = true;
    const el = document.createElement('span');
    el.textContent = '$1,000';
    document.body.append(el);
    hook(vCountUp, 'mounted', el);

    const frames: string[] = [];
    runCount(el, frames);
    el.textContent = '$2,000';
    hook(vCountUp, 'updated', el);

    expect(frames[0]).toBe('$1,000');
    expect(frames[frames.length - 1]).toBe('$2,000');
    expect(el.textContent).toBe('$2,000');
  });

  it.each(['-', '∞', '$-'])('leaves %s exactly as rendered', (unparsable) => {
    state.motionOn = true;
    const { to } = stubTweens();
    const el = document.createElement('span');
    el.textContent = '$1,000';
    document.body.append(el);
    hook(vCountUp, 'mounted', el);

    el.textContent = unparsable;
    hook(vCountUp, 'updated', el);

    expect(el.textContent).toBe(unparsable);
    expect(to).not.toHaveBeenCalled();
  });

  it.each(['-', '∞', '$-'])('does not count away from %s either', (unparsable) => {
    state.motionOn = true;
    const { to } = stubTweens();
    const el = document.createElement('span');
    el.textContent = unparsable;
    document.body.append(el);
    hook(vCountUp, 'mounted', el);

    el.textContent = '$2,000';
    hook(vCountUp, 'updated', el);

    expect(el.textContent).toBe('$2,000');
    expect(to).not.toHaveBeenCalled();
  });

  it('stays quiet when the number did not change', () => {
    state.motionOn = true;
    const { to } = stubTweens();
    const el = document.createElement('span');
    el.textContent = '$1,000';
    document.body.append(el);
    hook(vCountUp, 'mounted', el);

    hook(vCountUp, 'updated', el);

    expect(to).not.toHaveBeenCalled();
  });
});
