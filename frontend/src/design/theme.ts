/**
 * Look, mode and motion — the three appearance choices, and how they reach
 * the DOM.
 *
 * - **Look** (`data-look` on `<html>`): which token sheet applies. See
 *   `./looks.ts` and `src/assets/looks/`.
 * - **Mode** (`.dark` on `<html>` + `style.colorScheme`): light, dark, or
 *   follow the OS. Tailwind's `darkMode: 'class'` and the look sheets' dark
 *   rules both key off the class.
 * - **Motion** (`data-motion="reduced"` on `<html>`): an in-app switch that
 *   `motionEnabled()` and the CSS neutraliser honour alongside the OS setting.
 *
 * Persistence is **per browser, not per user** — the app has no accounts.
 * Choices live in `localStorage`, which the browser keeps per profile and per
 * site until changed: two people on two machines each keep their own look, a
 * shared machine keeps the last choice made there, a private window starts
 * from the defaults. `localStorage` rather than a cookie because a cookie
 * would ride on every request to the backend (which must not change) and
 * because the inline script in `index.html` reads it before the first frame,
 * so there is no flash. The keys here and the literals in that script must
 * agree; `theme.test.ts` holds them together.
 *
 * Every DOM write is guarded, so importing this module in a test or on a host
 * without a document is harmless. The refs are module singletons: the shell,
 * the Settings drawer and the chart all read the same state.
 */
import { shallowRef, type Ref } from "vue";

import { resetMotionTokenCache } from "../motion/tokens";
import { resetChartTokenCache } from "./chartTokens";
import { DEFAULT_LOOK, LOOKS, isLookId, type Look, type LookId } from "./looks";

export type ThemeChoice = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";
export type MotionChoice = "full" | "reduced";

export const THEME_STORAGE_KEY = "bw.theme";
export const LOOK_STORAGE_KEY = "bw.look";
export const MOTION_STORAGE_KEY = "bw.motion";

/**
 * The mode a browser that has never chosen one gets: dark, since the UI v2
 * Phase 3 exit put every view on tokens. The pre-paint script in `index.html`
 * and `main.css`'s no-JS fallback carry the same default (`theme.test.ts`
 * holds the three together).
 */
export const DEFAULT_CHOICE: ThemeChoice = "dark";

export const themeChoice: Ref<ThemeChoice> = shallowRef<ThemeChoice>(DEFAULT_CHOICE);
export const resolvedTheme: Ref<ResolvedTheme> = shallowRef<ResolvedTheme>("dark");
export const look: Ref<LookId> = shallowRef<LookId>(DEFAULT_LOOK);
export const motionChoice: Ref<MotionChoice> = shallowRef<MotionChoice>("full");
/**
 * Bumped on every applied look or mode switch. A `computed` that reads
 * resolved token values (the chart's colours, a GSAP duration) depends on it
 * so it re-evaluates after the caches below were reset.
 */
export const themeEpoch: Ref<number> = shallowRef(0);

// ---------------------------------------------------------------------------
// storage (never throws: private windows and locked-down browsers reject writes)
// ---------------------------------------------------------------------------

function readStorage(key: string): string | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string): void {
  try {
    if (typeof localStorage !== "undefined") localStorage.setItem(key, value);
  } catch {
    // A choice that cannot be remembered still applies for this page.
  }
}

const isChoice = (value: unknown): value is ThemeChoice =>
  value === "light" || value === "dark" || value === "system";
const isMotion = (value: unknown): value is MotionChoice => value === "full" || value === "reduced";

export function readStoredChoice(): ThemeChoice | null {
  const stored = readStorage(THEME_STORAGE_KEY);
  return isChoice(stored) ? stored : null;
}

/** Unknown or retired ids read as "nothing stored", so a stale key can never break the page. */
export function readStoredLook(): LookId | null {
  const stored = readStorage(LOOK_STORAGE_KEY);
  return isLookId(stored) ? stored : null;
}

export function readStoredMotion(): MotionChoice | null {
  const stored = readStorage(MOTION_STORAGE_KEY);
  return isMotion(stored) ? stored : null;
}

// ---------------------------------------------------------------------------
// resolution
// ---------------------------------------------------------------------------

const DARK_SCHEME_QUERY = "(prefers-color-scheme: dark)";

/** The OS preference, or dark when the host cannot tell us (the app's own default). */
export function systemTheme(): ResolvedTheme {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return "dark";
  return window.matchMedia(DARK_SCHEME_QUERY).matches ? "dark" : "light";
}

export function resolveTheme(choice: ThemeChoice): ResolvedTheme {
  return choice === "system" ? systemTheme() : choice;
}

export function currentLook(): Look {
  return LOOKS.find((entry) => entry.id === look.value) ?? LOOKS[0]!;
}

// ---------------------------------------------------------------------------
// application (DOM only — nothing here touches storage)
// ---------------------------------------------------------------------------

const root = (): HTMLElement | null => (typeof document === "undefined" ? null : document.documentElement);

function invalidate(): void {
  // Both caches hold values resolved from the stylesheet under the previous
  // look/mode; the epoch tells every dependent computed to ask again.
  resetChartTokenCache();
  resetMotionTokenCache();
  themeEpoch.value += 1;
}

export function applyTheme(theme: ResolvedTheme): void {
  const html = root();
  if (html) {
    html.classList.toggle("dark", theme === "dark");
    html.style.colorScheme = theme;
  }
  resolvedTheme.value = theme;
  invalidate();
}

/** Looks whose fonts have been requested this page. Each look loads once. */
const fontsRequested = new Set<LookId>();

export function applyLook(id: LookId): void {
  const html = root();
  if (html) html.dataset.look = id;
  look.value = id;
  if (!fontsRequested.has(id)) {
    fontsRequested.add(id);
    const entry = LOOKS.find((candidate) => candidate.id === id);
    // A font that fails to load leaves the fallback stack rendering; never fatal.
    void entry?.loadFonts().catch(() => undefined);
  }
  invalidate();
}

export function applyMotion(choice: MotionChoice): void {
  const html = root();
  if (html) {
    if (choice === "reduced") html.dataset.motion = "reduced";
    else delete html.dataset.motion;
  }
  motionChoice.value = choice;
}

// ---------------------------------------------------------------------------
// the public setters (store, then apply)
// ---------------------------------------------------------------------------

export function setTheme(choice: ThemeChoice): void {
  writeStorage(THEME_STORAGE_KEY, choice);
  themeChoice.value = choice;
  applyTheme(resolveTheme(choice));
}

export function setLook(id: LookId): void {
  writeStorage(LOOK_STORAGE_KEY, id);
  applyLook(id);
}

export function setMotion(choice: MotionChoice): void {
  writeStorage(MOTION_STORAGE_KEY, choice);
  applyMotion(choice);
}

/** Flip to the explicit opposite of what is showing (so "system" becomes a fixed choice). */
export function toggleTheme(): void {
  setTheme(resolvedTheme.value === "dark" ? "light" : "dark");
}

// ---------------------------------------------------------------------------
// boot
// ---------------------------------------------------------------------------

let initialised = false;

/**
 * Apply the stored (or default) look, mode and motion, then keep following
 * the OS while the mode choice is "system" and keep two tabs in agreement.
 * Idempotent: `main.ts` calls it once; a second call is a no-op.
 */
export function initTheme(): void {
  if (initialised) return;
  initialised = true;

  themeChoice.value = readStoredChoice() ?? DEFAULT_CHOICE;
  applyLook(readStoredLook() ?? DEFAULT_LOOK);
  applyTheme(resolveTheme(themeChoice.value));
  applyMotion(readStoredMotion() ?? "full");

  if (typeof window === "undefined") return;

  if (typeof window.matchMedia === "function") {
    const media = window.matchMedia(DARK_SCHEME_QUERY);
    const follow = () => {
      if (themeChoice.value === "system") applyTheme(systemTheme());
    };
    if (typeof media.addEventListener === "function") media.addEventListener("change", follow);
  }

  window.addEventListener("storage", (event) => {
    if (event.key === THEME_STORAGE_KEY) {
      const choice = readStoredChoice() ?? DEFAULT_CHOICE;
      themeChoice.value = choice;
      applyTheme(resolveTheme(choice));
    } else if (event.key === LOOK_STORAGE_KEY) {
      applyLook(readStoredLook() ?? DEFAULT_LOOK);
    } else if (event.key === MOTION_STORAGE_KEY) {
      applyMotion(readStoredMotion() ?? "full");
    }
  });
}

/** Test hook: forget that `initTheme` ran and which fonts were requested. */
export function resetThemeForTests(): void {
  initialised = false;
  fontsRequested.clear();
  themeChoice.value = DEFAULT_CHOICE;
  resolvedTheme.value = "dark";
  look.value = DEFAULT_LOOK;
  motionChoice.value = "full";
  themeEpoch.value = 0;
}
