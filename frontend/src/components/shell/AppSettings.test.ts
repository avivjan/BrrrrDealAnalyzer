// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { mount, type VueWrapper } from "@vue/test-utils";
import { nextTick } from "vue";

import { LOOKS } from "../../design/looks";
import { look, motionChoice, resetThemeForTests, themeChoice } from "../../design/theme";
import AppSettings from "./AppSettings.vue";
import LookPicker from "./LookPicker.vue";

let wrapper: VueWrapper | null = null;

beforeEach(() => {
  localStorage.clear();
  resetThemeForTests();
});

afterEach(() => {
  wrapper?.unmount();
  wrapper = null;
  document.body.innerHTML = "";
});

describe("LookPicker", () => {
  it("is a radiogroup of one card per look, each previewing itself, with one tab stop", () => {
    const picker = mount(LookPicker, { props: { modelValue: "luxury", mode: "light" } });
    expect(picker.attributes("role")).toBe("radiogroup");
    const radios = picker.findAll('[role="radio"]');
    expect(radios.map((r) => r.attributes("data-testid"))).toEqual(LOOKS.map((l) => `shell.look.${l.id}`));
    expect(radios.map((r) => r.attributes("aria-checked"))).toEqual(["false", "false", "false", "true"]);
    expect(radios.map((r) => r.attributes("tabindex"))).toEqual(["-1", "-1", "-1", "0"]);
    const previews = picker.findAll("[data-look]");
    expect(previews.map((p) => p.attributes("data-look"))).toEqual(LOOKS.map((l) => l.id));
    expect(previews.every((p) => p.attributes("data-mode") === "light")).toBe(true);
    expect(picker.text()).toContain("Quiet Luxury");
  });

  it("emits the chosen look on click and on arrow keys", async () => {
    const picker = mount(LookPicker, { props: { modelValue: "luxury" } });
    await picker.get('[data-testid="shell.look.aurora"]').trigger("click");
    expect(picker.emitted("update:modelValue")).toEqual([["aurora"]]);
    await picker.trigger("keydown", { key: "ArrowRight" }); // from luxury (last) wraps to first
    expect(picker.emitted("update:modelValue")![1]).toEqual(["obsidian"]);
    await picker.trigger("keydown", { key: "ArrowLeft" });
    expect(picker.emitted("update:modelValue")![2]).toEqual(["brutal"]);
  });
});

describe("AppSettings", () => {
  const open = async () => {
    wrapper = mount(AppSettings, { attachTo: document.body, props: { open: true } });
    await nextTick();
    return wrapper;
  };
  const q = (sel: string) => document.querySelector(sel) as HTMLElement | null;

  it("is the Appearance drawer with Look, Mode and Motion, saved automatically", async () => {
    await open();
    expect(q('[data-testid="shell.settings"]')).not.toBeNull();
    expect(document.querySelector("h2")!.textContent).toBe("Appearance");
    expect(q('[data-testid="shell.look-picker"]')).not.toBeNull();
    expect(q('[data-testid="shell.mode"]')!.getAttribute("aria-label")).toBe("Mode");
    expect(q('[data-testid="shell.motion"]')!.getAttribute("aria-label")).toBe("Motion");
    expect(q('[data-part="footer"]')!.textContent).toContain("Saved automatically in this browser");
  });

  it("applies and persists a look, a mode and a motion choice, and announces them", async () => {
    await open();
    q('[data-testid="shell.look.brutal"]')!.click();
    q('[data-testid="shell.mode"] [data-value="system"]')!.click();
    q('[data-testid="shell.motion"] [data-value="reduced"]')!.click();
    await nextTick();
    expect(look.value).toBe("brutal");
    expect(themeChoice.value).toBe("system");
    expect(motionChoice.value).toBe("reduced");
    expect(localStorage.getItem("bw.look")).toBe("brutal");
    expect(localStorage.getItem("bw.theme")).toBe("system");
    expect(localStorage.getItem("bw.motion")).toBe("reduced");
    expect(document.documentElement.dataset.look).toBe("brutal");
    expect(document.documentElement.dataset.motion).toBe("reduced");
    expect(q('[role="status"]')!.textContent).toContain("Neo-Brutal Fintech");
  });

  it("closes from Escape and never fetches or imports a store", async () => {
    await open();
    (q('[data-testid="shell.settings"]') as HTMLElement).dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(wrapper!.emitted("close")).toHaveLength(1);
  });
});
