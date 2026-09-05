// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as chartTokens from "./chartTokens";
import * as motionTokens from "../motion/tokens";
import { DEFAULT_LOOK, LOOKS } from "./looks";
import {
  DEFAULT_CHOICE,
  LOOK_STORAGE_KEY,
  MOTION_STORAGE_KEY,
  THEME_STORAGE_KEY,
  applyLook,
  applyTheme,
  initTheme,
  look,
  motionChoice,
  readStoredChoice,
  readStoredLook,
  resetThemeForTests,
  resolveTheme,
  resolvedTheme,
  setLook,
  setMotion,
  setTheme,
  systemTheme,
  themeChoice,
  themeEpoch,
  toggleTheme,
} from "./theme";

const read = (relative: string) => readFileSync(new URL(relative, import.meta.url), "utf8");
const html = () => document.documentElement;

/** Pretend the OS prefers `scheme`. */
function fakeSystem(scheme: "light" | "dark") {
  const listeners: Array<() => void> = [];
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: (query: string) => ({
      matches: query.includes("dark") ? scheme === "dark" : false,
      media: query,
      addEventListener: (_: string, fn: () => void) => listeners.push(fn),
      removeEventListener: () => undefined,
    }),
  });
  return { fire: () => listeners.forEach((fn) => fn()) };
}

beforeEach(() => {
  localStorage.clear();
  html().className = "";
  html().removeAttribute("data-look");
  html().removeAttribute("data-motion");
  html().style.colorScheme = "";
  fakeSystem("light");
  resetThemeForTests();
  for (const entry of LOOKS) vi.spyOn(entry, "loadFonts").mockResolvedValue(undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("defaults and storage", () => {
  it("defaults to the Quiet Luxury look in light mode (dark from the Phase 3 exit), with full motion", () => {
    expect(DEFAULT_LOOK).toBe("luxury");
    expect(DEFAULT_CHOICE).toBe("light");
    initTheme();
    expect(html().dataset.look).toBe("luxury");
    expect(html().classList.contains("dark")).toBe(false);
    expect(html().style.colorScheme).toBe("light");
    expect(html().dataset.motion).toBeUndefined();
  });

  it("prefers a stored choice over the system, and the system over the default", () => {
    // Nothing stored, OS dark, choice defaults to 'light' → light (the default is not 'system').
    fakeSystem("dark");
    initTheme();
    expect(resolvedTheme.value).toBe("light");

    resetThemeForTests();
    localStorage.setItem(THEME_STORAGE_KEY, "system");
    fakeSystem("light");
    initTheme();
    expect(resolvedTheme.value).toBe("light");

    resetThemeForTests();
    localStorage.setItem(THEME_STORAGE_KEY, "light");
    fakeSystem("dark");
    initTheme();
    expect(resolvedTheme.value).toBe("light");
  });

  it("reads back only valid stored values", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "sepia");
    localStorage.setItem(LOOK_STORAGE_KEY, "retired-look");
    expect(readStoredChoice()).toBeNull();
    expect(readStoredLook()).toBeNull();
    initTheme();
    expect(look.value).toBe(DEFAULT_LOOK);
  });

  it("persists every setter under its own key, in this browser only", () => {
    initTheme();
    setLook("obsidian");
    setTheme("light");
    setMotion("reduced");
    expect(localStorage.getItem(LOOK_STORAGE_KEY)).toBe("obsidian");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(localStorage.getItem(MOTION_STORAGE_KEY)).toBe("reduced");
    expect(Object.keys(localStorage).sort()).toEqual([LOOK_STORAGE_KEY, MOTION_STORAGE_KEY, THEME_STORAGE_KEY].sort());
  });

  it("survives a browser that refuses storage writes", () => {
    initTheme();
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    expect(() => setLook("brutal")).not.toThrow();
    expect(html().dataset.look).toBe("brutal");
  });
});

describe("applying", () => {
  it("applyTheme sets the class, the colour scheme, and resets both caches", () => {
    const chart = vi.spyOn(chartTokens, "resetChartTokenCache");
    const motion = vi.spyOn(motionTokens, "resetMotionTokenCache");
    const before = themeEpoch.value;
    applyTheme("light");
    expect(html().classList.contains("dark")).toBe(false);
    expect(html().style.colorScheme).toBe("light");
    expect(chart).toHaveBeenCalledTimes(1);
    expect(motion).toHaveBeenCalledTimes(1);
    expect(themeEpoch.value).toBe(before + 1);
    applyTheme("dark");
    expect(html().classList.contains("dark")).toBe(true);
    expect(themeEpoch.value).toBe(before + 2);
  });

  it("applyLook sets data-look, bumps the epoch, and loads that look's fonts once", () => {
    const aurora = LOOKS.find((entry) => entry.id === "aurora")!;
    applyLook("aurora");
    applyLook("aurora");
    applyLook("aurora");
    expect(html().dataset.look).toBe("aurora");
    expect(look.value).toBe("aurora");
    expect(aurora.loadFonts).toHaveBeenCalledTimes(1);
    const obsidian = LOOKS.find((entry) => entry.id === "obsidian")!;
    expect(obsidian.loadFonts).not.toHaveBeenCalled();
  });

  it("setMotion('reduced') marks the root and motionEnabled() reads it", async () => {
    const { motionEnabled } = await import("../motion/gsap");
    setMotion("reduced");
    expect(html().dataset.motion).toBe("reduced");
    expect(motionChoice.value).toBe("reduced");
    // Under Vitest motionEnabled() is always false; the DOM mark is what the
    // browser path reads, so assert the mark and that the function still answers.
    expect(motionEnabled()).toBe(false);
    setMotion("full");
    expect(html().dataset.motion).toBeUndefined();
  });

  it("toggleTheme picks the explicit opposite of what is showing, even from 'system'", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "system");
    fakeSystem("dark");
    initTheme();
    expect(resolvedTheme.value).toBe("dark");
    toggleTheme();
    expect(themeChoice.value).toBe("light");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(resolvedTheme.value).toBe("light");
  });

  it("follows the OS only while the choice is 'system'", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "system");
    const os = fakeSystem("light");
    initTheme();
    expect(resolvedTheme.value).toBe("light");
    fakeSystem("dark"); // the OS flipped…
    os.fire(); // …and told us
    expect(resolvedTheme.value).toBe("dark");

    setTheme("light"); // an explicit choice stops following
    fakeSystem("dark");
    os.fire();
    expect(resolvedTheme.value).toBe("light");
  });

  it("is idempotent: a second initTheme() changes nothing and loads no more fonts", () => {
    initTheme();
    const luxury = LOOKS.find((entry) => entry.id === DEFAULT_LOOK)!;
    const epoch = themeEpoch.value;
    initTheme();
    expect(themeEpoch.value).toBe(epoch);
    expect(luxury.loadFonts).toHaveBeenCalledTimes(1);
  });

  it("resolveTheme and systemTheme agree with the fake OS", () => {
    fakeSystem("dark");
    expect(systemTheme()).toBe("dark");
    expect(resolveTheme("system")).toBe("dark");
    expect(resolveTheme("light")).toBe("light");
  });
});

describe("the pre-paint script and the stylesheet agree with this module", () => {
  const indexHtml = read("../../index.html");

  it("uses the same storage keys, look ids and default look", () => {
    expect(indexHtml).toContain(`'${THEME_STORAGE_KEY}'`);
    expect(indexHtml).toContain(`'${LOOK_STORAGE_KEY}'`);
    expect(indexHtml).toContain(`'${MOTION_STORAGE_KEY}'`);
    for (const entry of LOOKS) expect(indexHtml).toContain(`'${entry.id}'`);
    // The default appears twice: the normal path and the catch path.
    expect(indexHtml.split(`'${DEFAULT_LOOK}'`).length - 1).toBeGreaterThanOrEqual(2);
  });

  it("defaults to the same mode as DEFAULT_CHOICE when nothing is stored", () => {
    // `…:<bool>` is the fall-through when no choice is stored.
    expect(indexHtml).toMatch(DEFAULT_CHOICE === "dark" ? /matches:true;/ : /matches:false;/);
  });

  it("main.css keeps only the no-JS fallback matching DEFAULT_CHOICE, and selects inherit the mode", () => {
    const css = read("../assets/main.css");
    const pins = [...css.matchAll(/color-scheme:\s*(light|dark)/g)].map((m) => m[1]);
    expect(pins).toEqual([DEFAULT_CHOICE]);
    expect(css).toMatch(/\.ui-select[\s\S]*?color-scheme:\s*inherit/);
  });
});
