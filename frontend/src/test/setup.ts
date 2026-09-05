/**
 * Vitest global setup.
 *
 * Loaded for every test file, including the `scripts/audit/*.test.mjs` suites
 * that run under the `node` environment — so everything here is guarded on
 * `window` and this module is a true no-op outside jsdom.
 *
 * Only APIs jsdom genuinely lacks are installed, and (apart from the canvas
 * context, see below) only when missing, so a future jsdom that implements one
 * of them wins over the stub. The one non-polyfill is the global registration
 * at the end, which mirrors what `main.ts` does to the real app: the Ui*
 * primitives themselves (a registration, not a stub — the real ones render) and
 * pass-through stand-ins for the motion layer.
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

  // `main.ts` registers the Ui* primitives globally, so a view template writes
  // `<UiButton>` without importing it (the Phase 3 script freeze forbids the
  // import). A test that mounts such a view needs the same registration, so the
  // one map in `components/ui/register.ts` also goes on Test Utils' global
  // config. This is registration, not stubbing: the real primitives render.
  //
  // Both imports are dynamic and inside the guard on purpose. The
  // `scripts/audit/*.test.mjs` suites run under the `node` environment and
  // share this setup file; they must not pay for — or be broken by — Test
  // Utils and thirteen SFCs being loaded for them.
  const { config } = await import("@vue/test-utils");
  const { UI_COMPONENTS } = await import("../components/ui/register");
  config.global.components = { ...config.global.components, ...UI_COMPONENTS };

  // The motion layer is the other thing `main.ts` registers globally, and a
  // view template writes `<UiTransition preset="...">` and `v-press` for the
  // same reason: the Phase 3 script freeze forbids the import. Here, unlike the
  // primitives, these really are stubs. A component test asserts what a view
  // renders, not how it arrives, so the wrappers pass their slot straight
  // through and the directives do nothing at all — which is also what the real
  // ones do under Vitest, where `motionEnabled()` is false. `src/motion/*` has
  // its own tests for the animation itself.
  const { defineComponent, h } = await import("vue");
  const UiTransition = defineComponent({
    name: "UiTransition",
    props: { preset: { type: String, required: true }, appear: Boolean },
    setup(_props, { slots }) {
      return () => slots.default?.();
    },
  });
  const UiTransitionGroup = defineComponent({
    name: "UiTransitionGroup",
    props: { preset: { type: String, required: true }, tag: { type: String, default: "div" } },
    setup(props, { slots }) {
      return () => h(props.tag, {}, slots.default?.());
    },
  });
  config.global.components = { ...config.global.components, UiTransition, UiTransitionGroup };
  config.global.directives = {
    ...config.global.directives,
    reveal: {},
    press: {},
    "hover-lift": {},
    flash: {},
    "count-up": {},
  };
}

export {};
