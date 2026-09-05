/**
 * The named transitions `<UiTransition preset="…">` can play.
 *
 * A preset is a pair of Vue `<Transition>` JavaScript hooks, so the same three
 * promises hold for all of them:
 *
 *  1. `done` is always called — synchronously when motion is off, from
 *     `onComplete` when it is on. Vue holds the element in the DOM until then,
 *     so a preset that forgot would leak a node on every close.
 *  2. Enters `clearProps` what they tweened. The stylesheet, not an inline
 *     style left over from a tween, decides what the element looks like once it
 *     has arrived.
 *  3. Leaves make the element inert *first*. A fading modal is still on top of
 *     the page and still clickable; `pointer-events: none` before anything else
 *     is what stops the user from hitting a button that is on its way out.
 *
 * Timings come from `tokens.ts`, which mirrors `tokens.css`. Nothing here reads
 * a duration from CSS at runtime: `:css="false"` means Vue is waiting on us.
 */
import { gsap, motionEnabled } from './gsap';
import { DUR, EASE } from './tokens';

/**
 * The panel inside a modal overlay.
 *
 * A modal overlay is `position: fixed` and must cover the viewport from the
 * first frame — the `deep-link-open` e2e spec measures exactly that — so it may
 * only fade. The scale therefore goes on the panel it contains (`UiModalPanel`
 * marks itself with this attribute), and an overlay with no panel simply fades.
 */
export const MODAL_PANEL_SELECTOR = '[data-ui="modal-panel"]';

/** What every enter hands back to the stylesheet when it finishes. */
const CLEAR_PROPS = 'transform,opacity,filter';

/** The Vue `<Transition>` hooks one preset provides. */
export interface MotionPreset {
  /** Animate `el` in, then call `done`. */
  enter(el: HTMLElement, done: () => void): void;
  /** Animate `el` out, then call `done`. Absent means "Vue may remove it now". */
  leave?(el: HTMLElement, done: () => void): void;
  /** Vue interrupted the enter: stop and leave no inline style behind. */
  enterCancelled(el: HTMLElement): void;
  /** Vue interrupted the leave. Only present when `leave` is. */
  leaveCancelled?(el: HTMLElement): void;
}

/** Every preset name a template may write. */
export type PresetName = 'page' | 'modal' | 'modalEnterOnly' | 'fade' | 'slideUp' | 'listItem';

const ENTER: GSAPTweenVars = { duration: DUR.base, ease: EASE.standard };
const ENTER_FAST: GSAPTweenVars = { duration: DUR.fast, ease: EASE.standard };
const LEAVE_FAST: GSAPTweenVars = { duration: DUR.fast, ease: EASE.exit };

/** Stop whatever is running on `el` and hand it back to the stylesheet. */
function cancel(el: HTMLElement): void {
  gsap.killTweensOf(el);
  gsap.set(el, { clearProps: 'all' });
}

/** Build an `enter` that tweens `el` itself from `from` to `to`. */
function enterWith(from: GSAPTweenVars, to: GSAPTweenVars) {
  return function enter(el: HTMLElement, done: () => void): void {
    gsap.killTweensOf(el);
    if (!motionEnabled()) {
      gsap.set(el, { clearProps: 'all' });
      done();
      return;
    }
    gsap.fromTo(el, from, { ...to, overwrite: 'auto', clearProps: CLEAR_PROPS, onComplete: done });
  };
}

/** Build a `leave` that makes `el` inert, then tweens it to `to`. */
function leaveWith(to: GSAPTweenVars) {
  return function leave(el: HTMLElement, done: () => void): void {
    el.style.pointerEvents = 'none';
    if (!motionEnabled()) {
      done();
      return;
    }
    gsap.killTweensOf(el);
    gsap.to(el, { ...to, overwrite: 'auto', onComplete: done });
  };
}

/** `el` itself when it is the panel, the panel it contains, or nothing. */
function modalPanel(el: HTMLElement): HTMLElement | null {
  if (el.matches(MODAL_PANEL_SELECTOR)) return el;
  return el.querySelector<HTMLElement>(MODAL_PANEL_SELECTOR);
}

function modalEnter(el: HTMLElement, done: () => void): void {
  gsap.killTweensOf(el);
  if (!motionEnabled()) {
    gsap.set(el, { clearProps: 'all' });
    done();
    return;
  }
  const panel = modalPanel(el);
  if (panel === el) {
    // The transition wraps the panel directly, so one tween does both.
    gsap.fromTo(
      el,
      { opacity: 0, scale: 0.96 },
      { opacity: 1, scale: 1, ...ENTER, overwrite: 'auto', clearProps: CLEAR_PROPS, onComplete: done },
    );
    return;
  }
  // `done` rides the root tween: it is the one Vue is waiting on.
  gsap.fromTo(
    el,
    { opacity: 0 },
    { opacity: 1, ...ENTER, overwrite: 'auto', clearProps: CLEAR_PROPS, onComplete: done },
  );
  if (panel) {
    gsap.killTweensOf(panel);
    gsap.fromTo(
      panel,
      { scale: 0.96 },
      { scale: 1, ...ENTER, overwrite: 'auto', clearProps: CLEAR_PROPS },
    );
  }
}

function modalLeave(el: HTMLElement, done: () => void): void {
  el.style.pointerEvents = 'none';
  if (!motionEnabled()) {
    done();
    return;
  }
  gsap.killTweensOf(el);
  const panel = modalPanel(el);
  if (panel === el) {
    gsap.to(el, { opacity: 0, scale: 0.98, ...LEAVE_FAST, overwrite: 'auto', onComplete: done });
    return;
  }
  gsap.to(el, { opacity: 0, ...LEAVE_FAST, overwrite: 'auto', onComplete: done });
  if (panel) {
    gsap.killTweensOf(panel);
    gsap.to(panel, { scale: 0.98, ...LEAVE_FAST, overwrite: 'auto' });
  }
}

/**
 * The presets, by the name a template writes.
 *
 * Only `modal` and `listItem` animate out. Every other preset is enter-only on
 * purpose: a leave animation holds a node in the DOM after the app considers it
 * gone, which is the wrong trade for an error banner, a save-status chip or a
 * whole route.
 */
export const presets: Record<PresetName, MotionPreset> = {
  /** Route changes. Opacity only — a moving page fights the scroll position. */
  page: {
    enter: enterWith({ opacity: 0 }, { opacity: 1, ...ENTER }),
    enterCancelled: cancel,
  },

  /** Overlay fades, panel scales. Opens in 250 ms, closes in 150 ms. */
  modal: {
    enter: modalEnter,
    leave: modalLeave,
    enterCancelled: cancel,
    leaveCancelled: cancel,
  },

  /** The same opening, for overlays that must vanish the instant they close. */
  modalEnterOnly: {
    enter: modalEnter,
    enterCancelled: cancel,
  },

  /** The plainest arrival there is. */
  fade: {
    enter: enterWith({ opacity: 0 }, { opacity: 1, ...ENTER }),
    enterCancelled: cancel,
  },

  /** A panel that arrives from just below where it belongs. */
  slideUp: {
    enter: enterWith({ opacity: 0, y: 8 }, { opacity: 1, y: 0, ...ENTER }),
    enterCancelled: cancel,
  },

  /** One row of a list, short enough that a whole list still feels instant. */
  listItem: {
    enter: enterWith({ opacity: 0, y: 6 }, { opacity: 1, y: 0, ...ENTER_FAST }),
    leave: leaveWith({ opacity: 0, ...LEAVE_FAST }),
    enterCancelled: cancel,
    leaveCancelled: cancel,
  },
};

/**
 * The hook props `<Transition>` / `<TransitionGroup>` receive.
 *
 * Spelled `onEnter…` and bound with `v-bind`, not `v-on`: the compiler turns
 * `v-on="obj"` on a *component* into `toHandlers(obj, true)`, which rewrites a
 * camelCase key as `on:enterCancelled` rather than `onEnterCancelled` — a prop
 * the built-in transitions never read.
 */
export interface TransitionHooks {
  onEnter(el: Element, done: () => void): void;
  onEnterCancelled(el: Element): void;
  onLeave?(el: Element, done: () => void): void;
  onLeaveCancelled?(el: Element): void;
}

/**
 * Turn a preset into the hook props the two wrappers bind.
 *
 * An enter-only preset yields no `onLeave` key at all, rather than an `onLeave`
 * that calls `done()` straight away: with no such prop Vue removes the element
 * itself, on the same tick, with no hook to get wrong.
 */
export function transitionHooks(preset: MotionPreset): TransitionHooks {
  const { leave, leaveCancelled } = preset;
  const hooks: TransitionHooks = {
    onEnter: (el, done) => preset.enter(el as HTMLElement, done),
    onEnterCancelled: (el) => preset.enterCancelled(el as HTMLElement),
  };
  if (leave && leaveCancelled) {
    hooks.onLeave = (el, done) => leave(el as HTMLElement, done);
    hooks.onLeaveCancelled = (el) => leaveCancelled(el as HTMLElement);
  }
  return hooks;
}
