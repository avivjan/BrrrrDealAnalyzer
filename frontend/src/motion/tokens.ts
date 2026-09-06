/**
 * Motion tokens for GSAP, read from the active look.
 *
 * CSS states durations in milliseconds and eases as cubic-béziers; GSAP wants
 * seconds and its own ease names. Each look declares both forms
 * (`--dur-*`, `--ease-*` for CSS; `--gsap-ease-*` for GSAP), and this module
 * reads them off `<html>` at tween time — so `DUR.base` is 0.18 s in Obsidian
 * Terminal and 0.4 s in Quiet Luxury from the same preset code.
 *
 * Values are memoised per page and dropped by `resetMotionTokenCache()`,
 * which `src/design/theme.ts` calls on every look or mode switch. Without a
 * document (unit tests, SSR) the base values of `tokens.css` are returned,
 * and `tokens.test.ts` holds those to the stylesheet.
 *
 * No GSAP import and no side effects: importing this file must stay free.
 */

export type DurationName = "fast" | "base" | "slow";
export type EaseName = "standard" | "emphasized" | "exit";

/** `tokens.css` `:root` values — what renders when no look sheet applies. */
export const FALLBACK_DUR: Readonly<Record<DurationName, number>> = {
  fast: 0.15,
  base: 0.25,
  slow: 0.4,
};

export const FALLBACK_EASE: Readonly<Record<EaseName, string>> = {
  standard: "power2.out",
  emphasized: "power3.inOut",
  exit: "power1.in",
};

const cache = new Map<string, string>();

/** Drop the memoised values, so the next read asks the stylesheet again. */
export function resetMotionTokenCache(): void {
  cache.clear();
}

function readVar(name: string): string {
  const cached = cache.get(name);
  if (cached !== undefined) return cached;
  if (typeof document === "undefined") return "";
  let value = "";
  try {
    value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  } catch {
    value = "";
  }
  cache.set(name, value);
  return value;
}

/** `'180ms'` → 0.18, `'0.4s'` → 0.4; anything else → NaN. */
export function parseSeconds(css: string): number {
  const match = /^(-?\d*\.?\d+)\s*(ms|s)$/.exec(css);
  if (!match) return Number.NaN;
  const amount = Number(match[1]);
  return match[2] === "ms" ? amount / 1000 : amount;
}

export function duration(name: DurationName): number {
  const seconds = parseSeconds(readVar(`--dur-${name}`));
  return Number.isFinite(seconds) ? seconds : FALLBACK_DUR[name];
}

export function ease(name: EaseName): string {
  return readVar(`--gsap-ease-${name}`) || FALLBACK_EASE[name];
}

/** Durations in seconds — `DUR.base` reads the active look each time it is asked. */
export const DUR: Readonly<Record<DurationName, number>> = {
  get fast() {
    return duration("fast");
  },
  get base() {
    return duration("base");
  },
  get slow() {
    return duration("slow");
  },
};

/** GSAP ease names, per the active look. */
export const EASE: Readonly<Record<EaseName, string>> = {
  get standard() {
    return ease("standard");
  },
  get emphasized() {
    return ease("emphasized");
  },
  get exit() {
    return ease("exit");
  },
};
