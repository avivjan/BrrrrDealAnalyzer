/**
 * The valueless motion directives.
 *
 * Phase 4 may not add a line to any view's `<script setup>`, so a directive
 * here never reads `binding.value` — there is no expression to read. A template
 * writes `v-press` or `v-reveal.stagger` and that is the entire contract: the
 * element itself, and at most one modifier.
 *
 * Three rules hold for all five, because each one decorates an element some
 * other component owns:
 *
 *  - Nothing happens when `motionEnabled()` is false. No tween, and no listener
 *    either: a reduced-motion user should not pay for handlers that would do
 *    nothing.
 *  - Listeners are passive and never call `preventDefault` or
 *    `stopPropagation`. A press effect that swallowed a pointer event would
 *    break the button it was decorating.
 *  - `unmounted` kills the tweens, removes the listeners and clears the inline
 *    styles, so a removed node leaves nothing running behind it.
 */
import type { ObjectDirective } from 'vue';

import { CLEAR_PROPS, gsap, motionEnabled } from './gsap';
import { DUR, EASE } from './tokens';

/** The attribute a child must carry to be part of a `v-reveal.stagger`. */
export const REVEAL_CHILD_SELECTOR = '[data-reveal]';

/** How long `v-flash` tints a value that just changed, in seconds. */
export const FLASH_DURATION = 0.4;

/**
 * The stagger ease. A slight overshoot reads as "these arrived" rather than
 * "these faded", which is the point of a reveal; it stays off dense tables,
 * where the same overshoot reads as sloppy.
 */
const REVEAL_STAGGER_EASE = 'back.out(1.4)';

/** Seconds between two staggered children. */
const REVEAL_STAGGER_EACH = 0.06;

/** `--color-primary` when the stylesheet cannot be read (indigo-600). */
const FLASH_FALLBACK_RGB = '79, 70, 229';

type Listener = [type: string, handler: EventListener];

/** Listeners a directive attached, so `unmounted` can take them off again. */
const listeners = new WeakMap<HTMLElement, Listener[]>();

/** Children a `v-reveal.stagger` has already animated. */
const revealed = new WeakSet<Element>();

/**
 * The staggered tweens each `v-reveal.stagger` element still has running.
 *
 * A staggered `fromTo` is not a plain tween: GSAP wraps the per-child tweens in
 * an internal timeline, and `killTweensOf(children)` kills the inner ones while
 * that wrapper stays on the global timeline. Keeping the handles is the only
 * way to remove it, and the global timeline being empty after an unmount is
 * exactly what the e2e motion guard checks.
 *
 * A *set*, not a single handle: a list that appends twice in quick succession
 * has two batches in flight, and killing the first to make room for the second
 * would freeze that batch's children half-faded with no `onComplete` left to
 * clear them. Each tween drops itself from the set when it finishes.
 */
const revealTweens = new WeakMap<HTMLElement, Set<GSAPTween>>();

/** The text `v-flash` last saw on an element. */
const flashText = new WeakMap<HTMLElement, string>();

/** The text `v-count-up` last saw on an element. */
const countText = new WeakMap<HTMLElement, string>();

/** The number object `v-count-up` tweens (the element's text is not a tween target). */
const counters = new WeakMap<HTMLElement, { value: number }>();

/** Attach `entries` passively and remember them. */
function listen(el: HTMLElement, entries: Listener[]): void {
  for (const [type, handler] of entries) {
    el.addEventListener(type, handler, { passive: true });
  }
  listeners.set(el, entries);
}

/** Undo `listen`. */
function unlisten(el: HTMLElement): void {
  const entries = listeners.get(el);
  if (!entries) return;
  for (const [type, handler] of entries) el.removeEventListener(type, handler);
  listeners.delete(el);
}

/**
 * The shared `unmounted`: stop everything and hand the element back.
 *
 * `[data-reveal]` descendants are a second target: `v-reveal.stagger` tweens
 * them rather than the element, so killing only the element would leave a
 * stagger running against nodes that are on their way out of the document.
 */
function release(el: HTMLElement): void {
  unlisten(el);
  for (const tween of revealTweens.get(el) ?? []) tween.kill();
  revealTweens.delete(el);
  gsap.killTweensOf(el);
  gsap.set(el, { clearProps: CLEAR_PROPS });
  const children = el.querySelectorAll(REVEAL_CHILD_SELECTOR);
  if (children.length > 0) {
    gsap.killTweensOf(children);
    gsap.set(children, { clearProps: CLEAR_PROPS });
  }
}

/** True when the device has a real pointer that can hover. */
function hoverSupported(): boolean {
  if (typeof window === 'undefined') return false;
  if (typeof window.matchMedia !== 'function') return false;
  return window.matchMedia('(hover: hover)').matches;
}

/** `--color-primary` as an `r, g, b` list, for the flash tint. */
function tintRgb(el: HTMLElement): string {
  if (typeof window === 'undefined' || typeof window.getComputedStyle !== 'function') {
    return FLASH_FALLBACK_RGB;
  }
  // The token is a space-separated triplet so Tailwind can slot alpha in;
  // GSAP's colour parser wants the comma-separated `rgba()` spelling.
  const parts = window
    .getComputedStyle(el)
    .getPropertyValue('--color-primary')
    .trim()
    .split(/[\s,]+/)
    .filter(Boolean);
  return parts.length === 3 ? parts.join(', ') : FLASH_FALLBACK_RGB;
}

/** Animate every `[data-reveal]` child that has not been revealed yet. */
function revealChildren(el: HTMLElement): void {
  const pending = Array.from(
    el.querySelectorAll<HTMLElement>(REVEAL_CHILD_SELECTOR),
  ).filter((child) => !revealed.has(child));
  if (pending.length === 0) return;
  for (const child of pending) revealed.add(child);
  const live = revealTweens.get(el) ?? new Set<GSAPTween>();
  revealTweens.set(el, live);
  // Declared before the call so `onComplete` can close over the handle; the
  // tween runs for `DUR.slow`, so the callback never fires before assignment.
  let tween: GSAPTween | undefined;
  tween = gsap.fromTo(
    pending,
    { opacity: 0, y: 8 },
    {
      opacity: 1,
      y: 0,
      duration: DUR.slow,
      ease: REVEAL_STAGGER_EASE,
      stagger: { each: REVEAL_STAGGER_EACH },
      overwrite: 'auto',
      clearProps: 'transform,opacity',
      onComplete: () => {
        if (tween) live.delete(tween);
      },
    },
  );
  live.add(tween);
}

/**
 * `v-reveal` / `v-reveal.stagger` — an entrance for content that arrives after
 * the first paint (a results panel, a freshly loaded list).
 *
 * Bare, it reveals the element. With `.stagger` it leaves the element alone and
 * walks its `[data-reveal]` children instead, which is what a container wants:
 * the box is already in the layout, the rows inside it are what is new. A
 * `WeakSet` remembers which children have run, so a re-render that appends two
 * rows animates two rows, not the whole list again.
 */
export const vReveal: ObjectDirective<HTMLElement> = {
  mounted(el, binding) {
    if (!motionEnabled()) return;
    if (binding.modifiers.stagger) {
      revealChildren(el);
      return;
    }
    gsap.fromTo(
      el,
      { opacity: 0, y: 8 },
      {
        opacity: 1,
        y: 0,
        duration: DUR.slow,
        ease: EASE.standard,
        overwrite: 'auto',
        clearProps: 'transform,opacity',
      },
    );
  },
  updated(el, binding) {
    if (!motionEnabled()) return;
    if (!binding.modifiers.stagger) return;
    revealChildren(el);
  },
  unmounted: release,
};

/**
 * `v-press` — the element gives a little under the finger.
 *
 * Restored on `pointerup`, `pointercancel` *and* `pointerleave`, so a pointer
 * that slides off the control never leaves it stuck at 97 %.
 */
export const vPress: ObjectDirective<HTMLElement> = {
  mounted(el) {
    if (!motionEnabled()) return;
    const down = (): void => {
      gsap.to(el, { scale: 0.97, duration: DUR.fast, ease: EASE.standard, overwrite: 'auto' });
    };
    const up = (): void => {
      gsap.to(el, {
        scale: 1,
        duration: DUR.fast,
        ease: EASE.standard,
        overwrite: 'auto',
        clearProps: 'transform',
      });
    };
    listen(el, [
      ['pointerdown', down],
      ['pointerup', up],
      ['pointercancel', up],
      ['pointerleave', up],
    ]);
  },
  unmounted: release,
};

/**
 * `v-hover-lift` — two pixels of rise under a real pointer.
 *
 * Gated on `(hover: hover)`: on a touch screen `pointerenter` fires on tap and
 * never gets its matching leave, so the element would simply stay lifted.
 */
export const vHoverLift: ObjectDirective<HTMLElement> = {
  mounted(el) {
    if (!motionEnabled()) return;
    if (!hoverSupported()) return;
    const enter = (): void => {
      gsap.to(el, { y: -2, duration: DUR.fast, ease: EASE.standard, overwrite: 'auto' });
    };
    const leave = (): void => {
      gsap.to(el, {
        y: 0,
        duration: DUR.fast,
        ease: EASE.standard,
        overwrite: 'auto',
        clearProps: 'transform',
      });
    };
    listen(el, [
      ['pointerenter', enter],
      ['pointerleave', leave],
    ]);
  },
  unmounted: release,
};

/**
 * `v-flash` — a value that changed tints its own background for 400 ms.
 *
 * The text is compared, never written: the number on screen is Vue's, and this
 * directive only says "look here". The tint is `--color-primary` at 14 %, read
 * from the element so it follows the theme, fading to transparent.
 *
 * `mounted` records the text even when motion is off, so the first change after
 * the user turns animation back on is still recognised as a change.
 */
export const vFlash: ObjectDirective<HTMLElement> = {
  mounted(el) {
    flashText.set(el, el.textContent ?? '');
  },
  updated(el) {
    const text = el.textContent ?? '';
    const previous = flashText.get(el);
    flashText.set(el, text);
    if (!motionEnabled()) return;
    if (previous === undefined || previous === text) return;
    const rgb = tintRgb(el);
    gsap.fromTo(
      el,
      { backgroundColor: `rgba(${rgb}, 0.14)` },
      {
        backgroundColor: `rgba(${rgb}, 0)`,
        duration: FLASH_DURATION,
        ease: EASE.exit,
        overwrite: 'auto',
        clearProps: 'backgroundColor',
      },
    );
  },
  unmounted: release,
};

/** The first number in a string: optional sign, thousands separators, decimals. */
const NUMBER_PATTERN = /-?\d[\d,]*(?:\.\d+)?/;

/** The number inside `text`, or null when there is not exactly one to read. */
function parseNumber(text: string): number | null {
  const match = NUMBER_PATTERN.exec(text);
  if (!match) return null;
  const value = Number(match[0].replace(/,/g, ''));
  return Number.isFinite(value) ? value : null;
}

/**
 * `value`, written the way `template`'s own number is written, in place.
 *
 * Keeps whatever surrounds it — `$`, `%`, ` yr` — and matches the target's
 * grouping and decimal places, so an intermediate frame never looks like a
 * different kind of number than the one that lands.
 */
function formatLike(template: string, value: number): string {
  const match = NUMBER_PATTERN.exec(template);
  if (!match) return template;
  const sample = match[0];
  const decimals = sample.includes('.') ? (sample.split('.')[1] ?? '').length : 0;
  const formatted = value.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
    useGrouping: sample.includes(','),
  });
  return template.replace(NUMBER_PATTERN, formatted);
}

/**
 * `v-count-up` — a number that changed counts to its new value.
 *
 * Two things keep it honest. It parses both the old and the new rendered text
 * and does nothing unless *both* are numbers, so the app's `-`, `∞` and `$-`
 * placeholders are left exactly as Vue wrote them. And the final frame is the
 * rendered string itself rather than a re-formatted number, so no rounding of
 * ours ever survives the tween.
 *
 * The tween target is a plain `{ value }` object; the element's text is written
 * from `onUpdate`.
 */
export const vCountUp: ObjectDirective<HTMLElement> = {
  mounted(el) {
    countText.set(el, el.textContent ?? '');
  },
  updated(el) {
    const target = el.textContent ?? '';
    const previous = countText.get(el) ?? '';
    countText.set(el, target);
    if (!motionEnabled()) return;

    const to = parseNumber(target);
    const from = parseNumber(previous);
    if (to === null || from === null || to === from) return;

    const counter = counters.get(el) ?? { value: from };
    counter.value = from;
    counters.set(el, counter);
    gsap.killTweensOf(counter);
    gsap.to(counter, {
      value: to,
      duration: DUR.slow,
      ease: EASE.standard,
      overwrite: 'auto',
      onUpdate: () => {
        el.textContent = formatLike(target, counter.value);
      },
      onComplete: () => {
        el.textContent = target;
      },
    });
  },
  unmounted(el) {
    const counter = counters.get(el);
    if (counter) {
      gsap.killTweensOf(counter);
      counters.delete(el);
    }
    release(el);
  },
};
