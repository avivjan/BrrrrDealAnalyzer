// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent } from "vue";
import { config, mount } from "@vue/test-utils";

import { UI_COMPONENTS, registerUiPrimitives } from "./register";

/**
 * The primitives are used by name, never imported: Phase 3 freezes every
 * `<script>` block, so a view that adopts `<UiButton>` cannot add the import
 * line. That only works while two registrations stay true — `main.ts` for the
 * running app (`registerUiPrimitives`) and `src/test/setup.ts` for anything a
 * test mounts (`config.global.components`) — so both are asserted here.
 */
const EXPECTED_NAMES = [
  "UiButton",
  "UiIconButton",
  "UiCard",
  "UiBadge",
  "UiStatTile",
  "UiField",
  "UiModalPanel",
  "UiSectionHeader",
  "UiEmptyState",
  "UiSkeleton",
  "UiSaveStatus",
  "UiTabs",
  "UiStepper",
];

/** A view-shaped component: it names two primitives and imports neither. */
const Consumer = defineComponent({
  template: `<UiCard><UiButton data-testid="register.button">Analyze</UiButton></UiCard>`,
});

/** Vue reports an unresolved tag through `console.warn`, and renders nothing useful. */
function captureWarnings() {
  return vi.spyOn(console, "warn").mockImplementation(() => {});
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("UI_COMPONENTS", () => {
  it("holds exactly the thirteen presentational primitives", () => {
    expect(Object.keys(UI_COMPONENTS)).toEqual(EXPECTED_NAMES);
  });
});

describe("registerUiPrimitives", () => {
  it("registers every primitive on the app it is given", () => {
    const app = createApp({ template: "<div />" });
    registerUiPrimitives(app);
    for (const name of EXPECTED_NAMES) {
      expect(app.component(name), `${name} is not registered`).toBe(
        UI_COMPONENTS[name as keyof typeof UI_COMPONENTS],
      );
    }
  });

  it("resolves the primitives a template names but never imports", () => {
    // Emptied for this test so the plugin, not the setup file, is what resolves them.
    const registered = config.global.components;
    config.global.components = {};
    const warn = captureWarnings();
    try {
      const wrapper = mount(Consumer, {
        global: { plugins: [{ install: registerUiPrimitives }] },
      });
      expect(wrapper.get('[data-testid="register.button"]').element.tagName).toBe("BUTTON");
      expect(warn).not.toHaveBeenCalled();
    } finally {
      config.global.components = registered;
    }
  });

  it("without it, the same template resolves nothing", () => {
    const registered = config.global.components;
    config.global.components = {};
    const warn = captureWarnings();
    try {
      mount(Consumer);
      expect(warn.mock.calls.join(" ")).toContain("Failed to resolve component");
    } finally {
      config.global.components = registered;
    }
  });
});

describe("the Vitest setup file", () => {
  it("has registered the same primitives on Test Utils' global config", () => {
    for (const name of EXPECTED_NAMES) {
      expect(config.global.components[name], `${name} is not registered`).toBe(
        UI_COMPONENTS[name as keyof typeof UI_COMPONENTS],
      );
    }
  });

  it("resolves them in a mount that installs no plugins", () => {
    const warn = captureWarnings();
    const wrapper = mount(Consumer);
    expect(wrapper.get('[data-testid="register.button"]').element.tagName).toBe("BUTTON");
    expect(warn).not.toHaveBeenCalled();
  });
});
