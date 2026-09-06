/**
 * The `prefers-reduced-motion` read, on its own so it can be asked anywhere.
 *
 * The default is *reduced*: a host with no `matchMedia` — SSR, an old browser,
 * a test environment — cannot tell us what the user wants, and the safe answer
 * to "may I animate this?" when nobody knows is no. `main.css` carries the same
 * preference in CSS for everything GSAP never touches.
 *
 * Read live rather than cached, because the setting can change while the page
 * is open (macOS and iOS both flip it without a reload).
 */

/** The media query the whole app agrees means "animate as little as possible". */
export const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

/** True when the user asked for reduced motion, or when we cannot ask. */
export function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return true;
  if (typeof window.matchMedia !== 'function') return true;
  return window.matchMedia(REDUCED_MOTION_QUERY).matches;
}
