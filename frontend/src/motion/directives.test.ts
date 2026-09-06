// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { DirectiveBinding, ObjectDirective } from 'vue';

import { CLEAR_PROPS, gsap } from './gsap';
import { DUR } from './tokens';
import {
  FLASH_DURATION,
  REVEAL_CHILD_SELECTOR,
  TILT_MAX_DEG,
  vCountUp,
  vFlash,
  vHoverLift,
  vPress,
  vReveal,
  vTilt,
} from './directives';

/**
 * The directives.
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
  ['v-tilt', vTilt],
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
    ['v-tilt', vTilt, ['pointerenter', 'pointermove', 'pointerleave']],
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

  /**
   * Two pointer directives on one element — `v-press v-hover-lift` on a card is
   * the obvious pairing — used to share a single WeakMap slot, so whichever
   * mounted second silently replaced the first one's handler list. The first
   * directive's listeners then survived every unmount: a detached node kept
   * four live `pointer*` handlers, and `gsap.to` still ran against it.
   */
  it('keeps two directives on one element from overwriting each other', () => {
    state.motionOn = true;
    const { to } = stubTweens();
    const el = document.createElement('button');
    document.body.append(el);
    const addEventListener = vi.spyOn(el, 'addEventListener');
    const removeEventListener = vi.spyOn(el, 'removeEventListener');

    hook(vPress, 'mounted', el);
    hook(vHoverLift, 'mounted', el);
    // v-press: pointerdown/up/cancel/leave. v-hover-lift: pointerenter/leave.
    expect(addEventListener).toHaveBeenCalledTimes(6);

    hook(vPress, 'unmounted', el);
    hook(vHoverLift, 'unmounted', el);

    expect(removeEventListener).toHaveBeenCalledTimes(6);
    to.mockClear();
    for (const type of ['pointerdown', 'pointerup', 'pointercancel', 'pointerenter', 'pointerleave']) {
      el.dispatchEvent(new Event(type, { bubbles: true }));
    }
    expect(to).not.toHaveBeenCalled();
  });

  it('takes only its own listeners off when one directive unmounts', () => {
    state.motionOn = true;
    const { to } = stubTweens();
    const el = document.createElement('button');
    document.body.append(el);

    hook(vPress, 'mounted', el);
    hook(vHoverLift, 'mounted', el);
    hook(vHoverLift, 'unmounted', el);

    to.mockClear();
    el.dispatchEvent(new Event('pointerenter', { bubbles: true }));
    expect(to).not.toHaveBeenCalled();

    el.dispatchEvent(new Event('pointerdown', { bubbles: true }));
    expect((to.mock.calls[0]?.[1] as Vars).scale).toBe(0.97);
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

describe('v-tilt', () => {
  /** A 200 × 100 box whose top-left corner sits at (100, 100). */
  const box = { left: 100, top: 100, width: 200, height: 100 } as const;

  /** Hold `getBoundingClientRect` to `box`, and count how often it is asked. */
  function withBox(el: HTMLElement): ReturnType<typeof vi.spyOn> {
    return vi.spyOn(el, 'getBoundingClientRect').mockReturnValue({
      ...box,
      right: box.left + box.width,
      bottom: box.top + box.height,
      x: box.left,
      y: box.top,
      toJSON: () => box,
    } as DOMRect);
  }

  /** Capture animation frames instead of running them. */
  function stubFrames(): {
    frames: FrameRequestCallback[];
    request: ReturnType<typeof vi.fn>;
    cancel: ReturnType<typeof vi.fn>;
  } {
    const frames: FrameRequestCallback[] = [];
    const request = vi.fn((callback: FrameRequestCallback) => {
      frames.push(callback);
      return frames.length;
    });
    const cancel = vi.fn();
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation(request);
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(cancel);
    return { frames, request, cancel };
  }

  /** A `pointer*` event at viewport coordinates (`x`, `y`). */
  function pointer(type: string, x: number, y: number): Event {
    return new MouseEvent(type, { bubbles: true, clientX: x, clientY: y });
  }

  /** Mount a tilting element under a real pointer, with frames captured. */
  function mountTilted(): {
    el: HTMLElement;
    rect: ReturnType<typeof withBox>;
    set: ReturnType<typeof vi.spyOn>;
  } & ReturnType<typeof stubFrames> {
    state.motionOn = true;
    const el = document.createElement('div');
    document.body.append(el);
    const rect = withBox(el);
    const set = vi.spyOn(gsap, 'set').mockImplementation((() => undefined) as never);
    const frames = stubFrames();
    hook(vTilt, 'mounted', el);
    return { el, rect, set, ...frames };
  }

  it('stays out of the way on a device with no hover', () => {
    state.motionOn = true;
    stubTweens();
    setHoverSupport(false);
    const el = document.createElement('div');
    document.body.append(el);
    const addEventListener = vi.spyOn(el, 'addEventListener');

    hook(vTilt, 'mounted', el);

    expect(addEventListener).not.toHaveBeenCalled();
  });

  it('promises the transform on enter and measures the box once', () => {
    const { el, rect, set } = mountTilted();

    el.dispatchEvent(pointer('pointerenter', 150, 125));
    el.dispatchEvent(pointer('pointermove', 150, 125));
    el.dispatchEvent(pointer('pointermove', 160, 130));

    expect(set).toHaveBeenCalledWith(el, { willChange: 'transform', transformPerspective: 800 });
    expect(rect).toHaveBeenCalledTimes(1);
  });

  it('paints a burst of moves in one frame, at the last position', () => {
    stubTweens();
    const { el, set, frames, request } = mountTilted();
    el.dispatchEvent(pointer('pointerenter', 200, 150));
    set.mockClear();

    // Three moves inside one frame: one request, and the frame reads the last.
    el.dispatchEvent(pointer('pointermove', 200, 150));
    el.dispatchEvent(pointer('pointermove', 250, 175));
    el.dispatchEvent(pointer('pointermove', 150, 125));
    expect(request).toHaveBeenCalledTimes(1);
    expect(set).not.toHaveBeenCalled();

    frames[0]?.(0);

    // (150, 125) in a box centred on (200, 150): half-way to the left edge
    // (dx = -50 of 100 → rotateY = -3°) and half-way to the top edge
    // (dy = -25 of 50 → rotateX = +3°, the card leaning up towards the pointer).
    expect(set).toHaveBeenCalledTimes(1);
    expect(set).toHaveBeenCalledWith(el, { rotateX: 3, rotateY: -3, transformPerspective: 800 });

    // The next move after a painted frame asks for a new one.
    el.dispatchEvent(pointer('pointermove', 250, 175));
    expect(request).toHaveBeenCalledTimes(2);
  });

  it('never rotates past six degrees', () => {
    stubTweens();
    const { el, set, frames } = mountTilted();
    el.dispatchEvent(pointer('pointerenter', 200, 150));
    set.mockClear();

    // Far outside the box on both axes: the raw values would be -12 and +18.
    el.dispatchEvent(pointer('pointermove', 0, 0));
    frames[0]?.(0);

    expect(set).toHaveBeenCalledWith(el, {
      rotateX: TILT_MAX_DEG,
      rotateY: -TILT_MAX_DEG,
      transformPerspective: 800,
    });
    expect(TILT_MAX_DEG).toBe(6);
  });

  it('creates no tween while the pointer is over the card', () => {
    const { to } = stubTweens();
    const { el, frames } = mountTilted();

    el.dispatchEvent(pointer('pointerenter', 200, 150));
    el.dispatchEvent(pointer('pointermove', 210, 160));
    frames[0]?.(0);

    expect(to).not.toHaveBeenCalled();
  });

  it('ignores a move that arrives before any enter', () => {
    const { el, request, set } = mountTilted();

    el.dispatchEvent(pointer('pointermove', 210, 160));

    expect(request).not.toHaveBeenCalled();
    expect(set).not.toHaveBeenCalled();
  });

  it('tweens back to flat on leave and hands the transform back', () => {
    const { to } = stubTweens();
    const { el, cancel, set } = mountTilted();
    el.dispatchEvent(pointer('pointerenter', 200, 150));
    el.dispatchEvent(pointer('pointermove', 210, 160));
    set.mockClear();

    el.dispatchEvent(pointer('pointerleave', 400, 400));

    expect(cancel).toHaveBeenCalledWith(1);
    expect(to).toHaveBeenCalledTimes(1);
    const [target, vars] = to.mock.calls[0] as [HTMLElement, Vars];
    expect(target).toBe(el);
    expect(vars).toMatchObject({
      rotateX: 0,
      rotateY: 0,
      duration: DUR.fast,
      overwrite: 'auto',
      clearProps: 'transform,willChange',
    });
    // The frame the leave cancelled has nothing left to paint.
    expect(set).not.toHaveBeenCalled();
  });

  it('cancels the pending frame on unmount and leaves no inline transform', () => {
    // Real `gsap.set`, so the inline style is what a browser would hold.
    state.motionOn = true;
    const el = document.createElement('div');
    document.body.append(el);
    withBox(el);
    const { frames, cancel } = stubFrames();
    hook(vTilt, 'mounted', el);

    el.dispatchEvent(pointer('pointerenter', 200, 150));
    expect(el.style.willChange).toBe('transform');
    el.dispatchEvent(pointer('pointermove', 210, 160));

    hook(vTilt, 'unmounted', el);

    expect(cancel).toHaveBeenCalledWith(1);
    expect(el.style.transform).toBe('');
    expect(el.style.willChange).toBe('');
    expect(gsap.globalTimeline.getChildren()).toHaveLength(0);

    // A frame the browser had already queued paints nothing either.
    frames[0]?.(0);
    expect(el.style.transform).toBe('');
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

  /**
   * The tween writes `el.textContent`, which replaces every child the element
   * had with one text node. That is only safe on an element that already *is*
   * one text node — the moment a template wraps the number in a `<span>`, or
   * puts an icon beside it, counting would delete that markup and never put it
   * back. Nothing in v1 attaches `v-count-up`; v2 will, so the guard lands now.
   */
  it('leaves an element that holds more than one node alone', () => {
    state.motionOn = true;
    const { to } = stubTweens();
    const el = document.createElement('span');
    el.innerHTML = '<i class="pi"></i>$1,000';
    document.body.append(el);
    hook(vCountUp, 'mounted', el);

    el.innerHTML = '<i class="pi"></i>$2,000';
    hook(vCountUp, 'updated', el);

    expect(to).not.toHaveBeenCalled();
    expect(el.innerHTML).toBe('<i class="pi"></i>$2,000');
    expect(el.childNodes).toHaveLength(2);
  });

  it('leaves an element whose only child is an element alone', () => {
    state.motionOn = true;
    const { to } = stubTweens();
    const el = document.createElement('span');
    el.innerHTML = '<b>$1,000</b>';
    document.body.append(el);
    hook(vCountUp, 'mounted', el);

    el.innerHTML = '<b>$2,000</b>';
    hook(vCountUp, 'updated', el);

    expect(to).not.toHaveBeenCalled();
    expect(el.innerHTML).toBe('<b>$2,000</b>');
  });

  it('still counts an element that is exactly one text node', () => {
    state.motionOn = true;
    const { to } = stubTweens();
    const el = document.createElement('span');
    el.textContent = '$1,000';
    document.body.append(el);
    hook(vCountUp, 'mounted', el);

    el.textContent = '$2,000';
    hook(vCountUp, 'updated', el);

    expect(to).toHaveBeenCalledTimes(1);
  });
});
