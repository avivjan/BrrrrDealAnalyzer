/**
 * Motion tokens for GSAP, mirroring `src/assets/tokens.css`.
 *
 * CSS states durations in milliseconds and eases as cubic-béziers; GSAP wants
 * seconds and its own ease names. These constants are the one place that
 * translation happens, and `tokens.test.ts` fails if the two ever drift.
 *
 * No GSAP import and no side effects: importing this file must stay free.
 */

/** Durations in seconds — `--dur-fast` / `--dur-base` / `--dur-slow`. */
export const DUR = {
  fast: 0.15,
  base: 0.25,
  slow: 0.4,
} as const;

/** GSAP ease names — `--ease-standard` / `--ease-emphasized` / `--ease-exit`. */
export const EASE = {
  standard: 'power2.out',
  emphasized: 'power3.inOut',
  exit: 'power1.in',
} as const;
