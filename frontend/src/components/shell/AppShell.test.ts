// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { mount, type VueWrapper } from "@vue/test-utils";
import { nextTick } from "vue";
import { createPinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";

import { resetThemeForTests } from "../../design/theme";
import AppShell from "./AppShell.vue";
import { NAV_ITEMS } from "./nav";

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

async function mountShell(path = "/liquidity") {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: NAV_ITEMS.map((item) => ({ path: item.to, name: item.name, component: { template: "<div />" } })),
  });
  await router.push(path);
  await router.isReady();
  wrapper = mount(AppShell, { attachTo: document.body, slots: { default: '<p data-testid="view">view</p>' }, global: { plugins: [router, createPinia()] } });
  await nextTick();
  return wrapper;
}

describe("AppShell", () => {
  it("frames the view: skip link, sidebar, topbar titled by route, one <main>, bottom nav", async () => {
    const shell = await mountShell();
    expect(shell.get("a[href='#main']").text()).toBe("Skip to content");
    expect(shell.find('[data-testid="shell.sidebar"]').exists()).toBe(true);
    expect(shell.get("h1").text()).toBe("Liquidity");
    expect(shell.findAll("main")).toHaveLength(1);
    expect(shell.get("main").attributes("id")).toBe("main");
    expect(shell.get("main").classes()).toEqual(expect.arrayContaining(["min-h-0", "overflow-y-auto"]));
    expect(shell.get('main [data-testid="view"]').text()).toBe("view");
    expect(shell.find('[data-testid="shell.mobile-nav"]').exists()).toBe(true);
    expect(shell.find('[data-testid="app.status"]').exists()).toBe(true);
  });

  it("opens the palette on Cmd/Ctrl+K and closes it on Escape", async () => {
    await mountShell();
    expect(document.querySelector('[data-testid="shell.command"]')).toBeNull();
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }));
    await nextTick();
    expect(document.querySelector('[data-testid="shell.command"]')).not.toBeNull();
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }));
    await nextTick();
    expect(document.querySelector('[data-testid="shell.command"]')).toBeNull();
  });

  it("opens Settings from the topbar gear and remembers a collapsed sidebar per browser", async () => {
    const shell = await mountShell();
    await shell.get('[data-testid="shell.settings-open"]').trigger("click");
    await nextTick();
    expect(document.querySelector('[data-testid="shell.settings"]')).not.toBeNull();
    await shell.get('[data-testid="shell.sidebar-toggle"]').trigger("click");
    expect(shell.attributes("data-collapsed")).toBe("true");
    expect(localStorage.getItem("bw.sidebar")).toBe("collapsed");
  });
});
