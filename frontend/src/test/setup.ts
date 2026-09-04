/**
 * Vitest global setup.
 *
 * Loaded for every test file, including the `scripts/audit/*.test.mjs` suites
 * that run under the `node` environment — so everything here is guarded on
 * `window` and this module is a true no-op outside jsdom.
 *
 * Only APIs jsdom genuinely lacks are installed, and (apart from the canvas
 * context, see below) only when missing, so a future jsdom that implements one
 * of them wins over the stub. Nothing here stubs a component or a directive;
 * that belongs to the test that needs it.
 */

/** Assign `value` at `key` only when the host has no implementation of its own. */
function defineIfMissing(target: object, key: string, value: unknown): void {
  if (key in target) return;
  Object.defineProperty(target, key, {
    value,
    writable: true,
    configurable: true,
  });
}

if (typeof window !== "undefined") {
  // `useMediaQuery` (@vueuse/core) calls this on mount; jsdom does no media
  // matching at all. `matches: false` means components render their
  // narrow/default branch.
  defineIfMissing(window, "matchMedia", (media: string) => ({
    matches: false,
    media,
    onchange: null,
    addEventListener() {},
    removeEventListener() {},
    addListener() {},
    removeListener() {},
    dispatchEvent() {
      return false;
    },
  }));

  // TimelineChart observes its canvas container to redraw on resize.
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  defineIfMissing(window, "ResizeObserver", ResizeObserverStub);
  defineIfMissing(globalThis, "ResizeObserver", ResizeObserverStub);

  // MyDeals scrolls the analysis results into view after an analyze.
  defineIfMissing(Element.prototype, "scrollIntoView", function scrollIntoView() {});

  // MyDeals' CSV export builds an object URL for a download link.
  defineIfMissing(URL, "createObjectURL", () => "blob:vitest");
  defineIfMissing(URL, "revokeObjectURL", () => {});

  // jsdom *has* HTMLCanvasElement.prototype.getContext, but without the native
  // `canvas` package it logs "Not implemented" and returns null — so
  // TimelineChart's `getContext('2d')!` would blow up on its first draw. This
  // one is therefore replaced unconditionally rather than only-when-missing.
  //
  // Every 2D call TimelineChart makes (setTransform, fillRect, arc, fillText,
  // stroke, setLineDash, …) is a no-op; the three that must return something
  // return the smallest shape that keeps arithmetic and gradient chaining
  // alive. Property assignments (fillStyle, font, textAlign, …) are stored.
  const measured = { width: 0 };
  const gradient = { addColorStop() {} };
  const context2d = new Proxy({} as Record<string, unknown>, {
    get(target, key: string) {
      if (key === "measureText") return () => measured;
      if (key === "createLinearGradient" || key === "createRadialGradient") {
        return () => gradient;
      }
      if (!(key in target)) target[key] = () => undefined;
      return target[key];
    },
    set(target, key: string, value: unknown) {
      target[key] = value;
      return true;
    },
  });
  Object.defineProperty(HTMLCanvasElement.prototype, "getContext", {
    value: () => context2d,
    writable: true,
    configurable: true,
  });
}

export {};
