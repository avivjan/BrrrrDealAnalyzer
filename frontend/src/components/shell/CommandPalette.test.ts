// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { nextTick } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

import { resetThemeForTests, look } from "../../design/theme";
import CommandPalette from "./CommandPalette.vue";
import { NAV_ITEMS } from "./nav";

let wrapper: VueWrapper | null = null;
let router: Router;

beforeEach(async () => {
  localStorage.clear();
  resetThemeForTests();
  router = createRouter({
    history: createMemoryHistory(),
    routes: NAV_ITEMS.map((item) => ({ path: item.to, name: item.name, component: { template: "<div />" } })),
  });
  await router.push("/");
  await router.isReady();
});

afterEach(() => {
  wrapper?.unmount();
  wrapper = null;
  document.body.innerHTML = "";
});

const open = async (props: Record<string, unknown> = {}) => {
  wrapper = mount(CommandPalette, { attachTo: document.body, props: { open: true, ...props }, global: { plugins: [router] } });
  await nextTick();
  await nextTick();
  return wrapper;
};
const q = <T extends Element>(sel: string) => document.querySelector<T>(sel);
const input = () => q<HTMLInputElement>('[data-testid="shell.command.input"]')!;
const options = () => [...document.querySelectorAll('[role="option"]')];

describe("CommandPalette", () => {
  it("is a modal dialog with a combobox over a listbox, focused on open", async () => {
    await open();
    expect(q('[data-testid="shell.command"]')).not.toBeNull();
    const dialog = q('[role="dialog"]')!;
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(input().getAttribute("role")).toBe("combobox");
    expect(input().getAttribute("aria-controls")).toBe(q('[role="listbox"]')!.id);
    expect(document.activeElement).toBe(input());
    expect(options().length).toBeGreaterThan(10);
    expect(options()[0]!.getAttribute("aria-selected")).toBe("true");
    expect(input().getAttribute("aria-activedescendant")).toBe(options()[0]!.id);
  });

  it("renders nothing while closed", async () => {
    await open({ open: false });
    expect(q('[data-testid="shell.command"]')).toBeNull();
  });

  it("filters as you type and runs the active command on Enter, closing first", async () => {
    await open();
    input().value = "liquid";
    input().dispatchEvent(new Event("input", { bubbles: true }));
    await nextTick();
    expect(options().map((o) => o.getAttribute("data-testid"))).toEqual(["shell.command.item.go-liquidity"]);
    input().dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    await nextTick();
    expect(wrapper!.emitted("close")).toHaveLength(1);
    await flushPromises();
    expect(router.currentRoute.value.path).toBe("/liquidity");
  });

  it("moves the active row with the arrow keys, wrapping", async () => {
    await open();
    const n = options().length;
    input().dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowUp", bubbles: true }));
    await nextTick();
    expect(options()[n - 1]!.getAttribute("aria-selected")).toBe("true");
    input().dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
    await nextTick();
    expect(options()[0]!.getAttribute("aria-selected")).toBe("true");
  });

  it("closes on Escape and on the scrim, and clicking a look command applies that look", async () => {
    await open();
    input().dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    (q('[data-testid="shell.command"]') as HTMLElement).click();
    expect(wrapper!.emitted("close")).toHaveLength(2);
    (q('[data-testid="shell.command.item.look-obsidian"]') as HTMLElement).click();
    expect(look.value).toBe("obsidian");
    (q('[data-testid="shell.command.item.settings"]') as HTMLElement).click();
    expect(wrapper!.emitted("openSettings")).toHaveLength(1);
  });

  it("restores focus to the opener on close", async () => {
    const trigger = document.createElement("button");
    document.body.appendChild(trigger);
    trigger.focus();
    await open({ open: false });
    await wrapper!.setProps({ open: true });
    await nextTick();
    await nextTick();
    expect(document.activeElement).toBe(input());
    await wrapper!.setProps({ open: false });
    await nextTick();
    expect(document.activeElement).toBe(trigger);
  });
});
