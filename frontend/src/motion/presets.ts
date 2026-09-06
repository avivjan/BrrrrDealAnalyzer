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
 *  4. Enters undo that first, whether they go on to animate or not. Vue reuses
 *     the same node for the next open, and `pointer-events` is the one thing
 *     `clearProps` is not allowed to remove — see `reviveEnter`.
 *
 * Timings come from `tokens.ts`, which reads the active look's `--dur-*` and
 * `--gsap-ease-*` off `<html>` — so they are read *when a tween starts*, never
 * captured at module load, and a look switch changes the tempo of the next
 * open. `:css="false"` means Vue is waiting on us for `done`.
 */
import { CLEAR_PROPS, gsap, motionEnabled } from './gsap';
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
export type PresetName =
  | 'page'
  | 'modal'
  | 'modalEnterOnly'
  | 'fade'
  | 'slideUp'
  | 'listItem'
  | 'commandPalette'
  | 'drawer'
  | 'hero';

/** Read at call time: `DUR`/`EASE` are getters over the active look. */
const ENTER = (): GSAPTweenVars => ({ duration: DUR.base, ease: EASE.standard });
const ENTER_FAST = (): GSAPTweenVars => ({ duration: DUR.fast, ease: EASE.standard });
const LEAVE_FAST = (): GSAPTweenVars => ({ duration: DUR.fast, ease: EASE.exit });

/**
 * Stop whatever is running on `el` and hand it back to the stylesheet.
 *
 * The modal panel is a second target: `modal` tweens it separately, so killing
 * only the root would leave a cancelled open with `scale(0.96)` frozen on the
 * panel — the tween that would have cleared it never reaches its `onComplete`.
 */
function cancel(el: HTMLElement): void {
  gsap.killTweensOf(el);
  gsap.set(el, { clearProps: CLEAR_PROPS });
  const panels = el.querySelectorAll(MODAL_PANEL_SELECTOR);
  if (panels.length > 0) {
    gsap.killTweensOf(panels);
    gsap.set(panels, { clearProps: CLEAR_PROPS });
  }
}

/**
 * `cancel`, plus the one thing `leave` did that `clearProps` no longer undoes.
 *
 * `leave` sets `pointer-events: none` as its very first act; an interrupted
 * leave means the element is staying, so it has to become clickable again.
 * `pointerEvents` is not in `CLEAR_PROPS` — nothing else should ever remove it
 * — so it is reset here explicitly.
 */
function cancelLeave(el: HTMLElement): void {
  el.style.pointerEvents = '';
  cancel(el);
}

/**
 * The one thing an arriving element has to undo before anything else.
 *
 * `leave` writes `pointer-events: none` and `CLEAR_PROPS` deliberately does not
 * list it, so an element that finished leaving keeps it. Vue reuses that same
 * node for the next open — a modal is one `v-if` node, not a fresh one per open
 * — so without this the reopened dialog would look right and swallow every
 * click. Cheap enough to do unconditionally, and it runs on the reduced-motion
 * path too, which is where most users are.
 */
function reviveEnter(el: HTMLElement): void {
  el.style.pointerEvents = '';
}

/** Build an `enter` that tweens `el` itself from `from` to `to()` (read per call). */
function enterWith(from: GSAPTweenVars, to: () => GSAPTweenVars) {
  return function enter(el: HTMLElement, done: () => void): void {
    reviveEnter(el);
    gsap.killTweensOf(el);
    if (!motionEnabled()) {
      gsap.set(el, { clearProps: CLEAR_PROPS });
      done();
      return;
    }
    gsap.fromTo(el, from, { ...to(), overwrite: 'auto', clearProps: CLEAR_PROPS, onComplete: done });
  };
}

/** Build a `leave` that makes `el` inert, then tweens it to `to()`. */
function leaveWith(to: () => GSAPTweenVars) {
  return function leave(el: HTMLElement, done: () => void): void {
    el.style.pointerEvents = 'none';
    if (!motionEnabled()) {
      done();
      return;
    }
    gsap.killTweensOf(el);
    gsap.to(el, { ...to(), overwrite: 'auto', onComplete: done });
  };
}

/** `el` itself when it is the panel, the panel it contains, or nothing. */
function modalPanel(el: HTMLElement): HTMLElement | null {
  if (el.matches(MODAL_PANEL_SELECTOR)) return el;
  return el.querySelector<HTMLElement>(MODAL_PANEL_SELECTOR);
}

function modalEnter(el: HTMLElement, done: () => void): void {
  reviveEnter(el);
  gsap.killTweensOf(el);
  if (!motionEnabled()) {
    gsap.set(el, { clearProps: CLEAR_PROPS });
    done();
    return;
  }
  const panel = modalPanel(el);
  if (panel === el) {
    // The transition wraps the panel directly, so one tween does both.
    gsap.fromTo(
      el,
      { opacity: 0, scale: 0.96 },
      { opacity: 1, scale: 1, ...ENTER(), overwrite: 'auto', clearProps: CLEAR_PROPS, onComplete: done },
    );
    return;
  }
  // `done` rides the root tween: it is the one Vue is waiting on.
  gsap.fromTo(
    el,
    { opacity: 0 },
    { opacity: 1, ...ENTER(), overwrite: 'auto', clearProps: CLEAR_PROPS, onComplete: done },
  );
  if (panel) {
    gsap.killTweensOf(panel);
    gsap.fromTo(
      panel,
      { scale: 0.96 },
      { scale: 1, ...ENTER(), overwrite: 'auto', clearProps: CLEAR_PROPS },
    );
  }
}

/**
 * Complex tier: the command palette. Overlay fades; the panel drops in from
 * 8 px above at 98% with the look's *emphasized* ease (a spring in Aurora,
 * near-linear in Obsidian), then its rows stagger in over 20 ms each. Three
 * tweens, `clearProps` on everything they touched; the whole thing is over
 * inside the 500 ms entrance budget in every look.
 */
function commandPaletteEnter(el: HTMLElement, done: () => void): void {
  reviveEnter(el);
  gsap.killTweensOf(el);
  if (!motionEnabled()) {
    gsap.set(el, { clearProps: CLEAR_PROPS });
    done();
    return;
  }
  // `done` rides the overlay tween: it is the one Vue is waiting on.
  gsap.fromTo(
    el,
    { opacity: 0 },
    { opacity: 1, duration: DUR.fast, ease: EASE.standard, overwrite: 'auto', clearProps: CLEAR_PROPS, onComplete: done },
  );
  const panel = modalPanel(el);
  if (!panel) return;
  gsap.killTweensOf(panel);
  gsap.fromTo(
    panel,
    { opacity: 0, y: -8, scale: 0.98 },
    { opacity: 1, y: 0, scale: 1, duration: DUR.base, ease: EASE.emphasized, overwrite: 'auto', clearProps: CLEAR_PROPS },
  );
  const rows = Array.from(panel.querySelectorAll<HTMLElement>('[role="option"]')).slice(0, 12);
  if (rows.length === 0) return;
  gsap.killTweensOf(rows);
  gsap.fromTo(
    rows,
    { opacity: 0, y: 4 },
    { opacity: 1, y: 0, duration: DUR.fast, ease: EASE.standard, stagger: 0.02, delay: DUR.fast * 0.5, overwrite: 'auto', clearProps: CLEAR_PROPS },
  );
}

/**
 * The marks a page header carries for the `hero` preset.
 *
 * `<UiTransition preset="hero" appear>` wraps the header block; inside it the
 * eyebrow, the title and each figure/action say which they are with
 * `data-hero="…"`. Anything unmarked is left alone.
 */
export const HERO_SELECTOR = {
  eyebrow: '[data-hero="eyebrow"]',
  title: '[data-hero="title"]',
  item: '[data-hero="item"]',
} as const;

/**
 * The whole header has arrived within this many seconds, whatever the look.
 *
 * Quiet Luxury is the slowest look (`--dur-fast: 200ms`, `--dur-base: 340ms`);
 * three sequential tweens at those tempos would run past 700 ms, so the
 * schedule below overlaps them and holds the total here.
 */
export const HERO_BUDGET = 0.45;

/** The step between one `[data-hero="item"]` and the next, when the budget allows it. */
export const HERO_STAGGER = 0.05;

/** Marked descendants only clear what the hero tweened on them. */
const HERO_CLEAR_PROPS = 'transform,opacity';

/** Where each part of a hero starts and how long it runs, in seconds. */
export interface HeroSchedule {
  /** Eyebrow and item duration (`DUR.fast`, capped). */
  fast: number;
  /** Title duration (`DUR.base`, capped). */
  base: number;
  /** When the title starts: part-way through the eyebrow. */
  titleAt: number;
  /** When the first item starts: part-way through the title. */
  itemsAt: number;
  /** The gap between consecutive items, squeezed when there are many. */
  stagger: number;
  /** When the last tween ends — never more than `HERO_BUDGET`. */
  total: number;
}

/**
 * Overlap the eyebrow, title and items so the last one ends inside the budget.
 *
 * The preferred shape: the title starts 40% into the eyebrow, the items start
 * halfway into the title, 50 ms apart. Each of those gives way in turn when the
 * look's tempo would overrun `HERO_BUDGET`: the title starts earlier, then the
 * items start earlier (never before the title), then the item stagger shrinks.
 * Durations themselves are capped so that a look with an absurd `--dur-*`
 * degrades to a fast header rather than a long one. Pure, so it can be checked
 * against any tempo without a DOM.
 */
export function heroSchedule(fast: number, base: number, items: number): HeroSchedule {
  const F = Math.min(Math.max(fast, 0), HERO_BUDGET / 2);
  const B = Math.min(Math.max(base, 0), HERO_BUDGET);
  const titleAt = Math.max(0, Math.min(F * 0.4, HERO_BUDGET - B));
  const titleEnd = titleAt + B;
  if (items <= 0) {
    return { fast: F, base: B, titleAt, itemsAt: titleEnd, stagger: 0, total: titleEnd };
  }
  let stagger = HERO_STAGGER;
  let itemsAt = titleAt + B * 0.5;
  const latestStart = HERO_BUDGET - F - (items - 1) * stagger;
  if (itemsAt > latestStart && latestStart >= titleAt) {
    itemsAt = latestStart;
  } else if (itemsAt > latestStart) {
    // Even alongside the title the run is too long at 50 ms a piece.
    itemsAt = titleAt;
    stagger = items > 1 ? Math.max(0, (HERO_BUDGET - F - titleAt) / (items - 1)) : 0;
  }
  const itemsEnd = itemsAt + (items - 1) * stagger + F;
  return { fast: F, base: B, titleAt, itemsAt, stagger, total: Math.max(titleEnd, itemsEnd) };
}

/**
 * The running hero timeline per header, so a cancel or a re-enter can kill
 * the whole thing — `killTweensOf(el)` only reaches tweens *of* `el`, and a
 * hero's tweens are of its descendants. Weak, so a header Vue discards is
 * not held here.
 */
const heroTimelines = new WeakMap<HTMLElement, gsap.core.Timeline>();

function heroMarks(el: HTMLElement): { eyebrows: HTMLElement[]; titles: HTMLElement[]; items: HTMLElement[] } {
  return {
    eyebrows: Array.from(el.querySelectorAll<HTMLElement>(HERO_SELECTOR.eyebrow)),
    titles: Array.from(el.querySelectorAll<HTMLElement>(HERO_SELECTOR.title)),
    items: Array.from(el.querySelectorAll<HTMLElement>(HERO_SELECTOR.item)),
  };
}

/** Stop a hero mid-flight and hand every mark back to the stylesheet. */
function heroCancel(el: HTMLElement): void {
  heroTimelines.get(el)?.kill();
  heroTimelines.delete(el);
  cancel(el);
  const { eyebrows, titles, items } = heroMarks(el);
  const marks = [...eyebrows, ...titles, ...items];
  if (marks.length > 0) {
    gsap.killTweensOf(marks);
    gsap.set(marks, { clearProps: HERO_CLEAR_PROPS });
  }
}

/**
 * Complex tier: a page header. The eyebrow rises 8 px, the title follows
 * 12 px on the standard ease, then the figures and actions cascade in — one
 * timeline whose `-=` offsets come from `heroSchedule`, so the whole header
 * has settled inside `HERO_BUDGET` in the slowest look. A header with no
 * marks at all still fades, so the preset is never a no-op.
 */
function heroEnter(el: HTMLElement, done: () => void): void {
  reviveEnter(el);
  // A re-enter mid-flight: stop the previous hero and clear its marks first,
  // or a look switch to reduced motion would freeze them half-faded.
  if (heroTimelines.has(el)) heroCancel(el);
  gsap.killTweensOf(el);
  if (!motionEnabled()) {
    gsap.set(el, { clearProps: CLEAR_PROPS });
    done();
    return;
  }
  const { eyebrows, titles, items } = heroMarks(el);
  const timeline = gsap.timeline({
    onComplete: () => {
      heroTimelines.delete(el);
      done();
    },
  });
  heroTimelines.set(el, timeline);

  if (eyebrows.length + titles.length + items.length === 0) {
    timeline.fromTo(
      el,
      { opacity: 0 },
      { opacity: 1, ...ENTER(), overwrite: 'auto', clearProps: CLEAR_PROPS },
    );
    return;
  }

  const plan = heroSchedule(DUR.fast, DUR.base, items.length);
  const ease = EASE.standard;
  const marks = [...eyebrows, ...titles, ...items];
  gsap.killTweensOf(marks);

  // Each `-=` is measured from the timeline's end as it stands, which is the
  // previous part's end — so the offset is that end minus the start the
  // schedule wants. A part that is absent is skipped and the next one starts
  // no later than the schedule says, measured from wherever the timeline ends.
  const at = (start: number): string => `-=${Math.max(0, timeline.duration() - start)}`;

  if (eyebrows.length > 0) {
    timeline.fromTo(
      eyebrows,
      { opacity: 0, y: 8 },
      { opacity: 1, y: 0, duration: plan.fast, ease, overwrite: 'auto', clearProps: HERO_CLEAR_PROPS },
      0,
    );
  }
  if (titles.length > 0) {
    timeline.fromTo(
      titles,
      { opacity: 0, y: 12 },
      { opacity: 1, y: 0, duration: plan.base, ease, overwrite: 'auto', clearProps: HERO_CLEAR_PROPS },
      at(plan.titleAt),
    );
  }
  if (items.length > 0) {
    timeline.fromTo(
      items,
      { opacity: 0, y: 8 },
      {
        opacity: 1,
        y: 0,
        duration: plan.fast,
        ease,
        stagger: plan.stagger,
        overwrite: 'auto',
        clearProps: HERO_CLEAR_PROPS,
      },
      at(plan.itemsAt),
    );
  }
}

/**
 * Complex tier: a side drawer. Scrim fades; the panel slides in from its own
 * edge (`data-side` on the panel says which) and fades. Leaves are the same
 * two motions reversed at `--dur-fast`, inert first like every leave.
 */
function drawerEnter(el: HTMLElement, done: () => void): void {
  reviveEnter(el);
  gsap.killTweensOf(el);
  if (!motionEnabled()) {
    gsap.set(el, { clearProps: CLEAR_PROPS });
    done();
    return;
  }
  const panel = modalPanel(el);
  const fromX = panel?.dataset.side === 'left' ? -24 : 24;
  gsap.fromTo(el, { opacity: 0 }, { opacity: 1, duration: DUR.fast, ease: EASE.standard, overwrite: 'auto', clearProps: CLEAR_PROPS, onComplete: done });
  if (panel) {
    gsap.killTweensOf(panel);
    gsap.fromTo(panel, { opacity: 0, x: fromX }, { opacity: 1, x: 0, duration: DUR.base, ease: EASE.emphasized, overwrite: 'auto', clearProps: CLEAR_PROPS });
  }
}

function drawerLeave(el: HTMLElement, done: () => void): void {
  el.style.pointerEvents = 'none';
  if (!motionEnabled()) {
    done();
    return;
  }
  gsap.killTweensOf(el);
  const panel = modalPanel(el);
  gsap.to(el, { opacity: 0, ...LEAVE_FAST(), overwrite: 'auto', onComplete: done });
  if (panel) {
    gsap.killTweensOf(panel);
    gsap.to(panel, { x: panel.dataset.side === 'left' ? -16 : 16, opacity: 0, ...LEAVE_FAST(), overwrite: 'auto' });
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
    gsap.to(el, { opacity: 0, scale: 0.98, ...LEAVE_FAST(), overwrite: 'auto', onComplete: done });
    return;
  }
  gsap.to(el, { opacity: 0, ...LEAVE_FAST(), overwrite: 'auto', onComplete: done });
  if (panel) {
    gsap.killTweensOf(panel);
    gsap.to(panel, { scale: 0.98, ...LEAVE_FAST(), overwrite: 'auto' });
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
    enter: enterWith({ opacity: 0 }, () => ({ opacity: 1, ...ENTER() })),
    enterCancelled: cancel,
  },

  /** Overlay fades, panel scales. Opens in `--dur-base`, closes in `--dur-fast`. */
  modal: {
    enter: modalEnter,
    leave: modalLeave,
    enterCancelled: cancel,
    leaveCancelled: cancelLeave,
  },

  /** The same opening, for overlays that must vanish the instant they close. */
  modalEnterOnly: {
    enter: modalEnter,
    enterCancelled: cancel,
  },

  /** The plainest arrival there is. */
  fade: {
    enter: enterWith({ opacity: 0 }, () => ({ opacity: 1, ...ENTER() })),
    enterCancelled: cancel,
  },

  /** A panel that arrives from just below where it belongs. */
  slideUp: {
    enter: enterWith({ opacity: 0, y: 8 }, () => ({ opacity: 1, y: 0, ...ENTER() })),
    enterCancelled: cancel,
  },

  /** Complex tier: the ⌘K palette — panel drops in on the emphasized ease, rows stagger. */
  commandPalette: {
    enter: commandPaletteEnter,
    leave: modalLeave,
    enterCancelled: cancel,
    leaveCancelled: cancelLeave,
  },

  /** Complex tier: a side drawer slides in from its edge. */
  drawer: {
    enter: drawerEnter,
    leave: drawerLeave,
    enterCancelled: cancel,
    leaveCancelled: cancelLeave,
  },

  /** Complex tier: a page header — eyebrow, then title, then figures, inside 450 ms. */
  hero: {
    enter: heroEnter,
    enterCancelled: heroCancel,
  },

  /** One row of a list, short enough that a whole list still feels instant. */
  listItem: {
    enter: enterWith({ opacity: 0, y: 6 }, () => ({ opacity: 1, y: 0, ...ENTER_FAST() })),
    leave: leaveWith(() => ({ opacity: 0, ...LEAVE_FAST() })),
    enterCancelled: cancel,
    leaveCancelled: cancelLeave,
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
  if (!leave) return hooks;
  if (!leaveCancelled) {
    // Loudly, not silently: dropping the leave to keep going would turn a
    // half-written preset into a transition that quietly never animates out.
    throw new Error(
      'motion preset: a preset that defines `leave` must also define ' +
        '`leaveCancelled`, or an interrupted close leaves the element ' +
        'mid-tween and `pointer-events: none`.',
    );
  }
  hooks.onLeave = (el, done) => leave(el as HTMLElement, done);
  hooks.onLeaveCancelled = (el) => leaveCancelled(el as HTMLElement);
  return hooks;
}
