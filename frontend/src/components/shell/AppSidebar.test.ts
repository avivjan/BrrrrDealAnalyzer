// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";

import { NAV_ITEMS } from "./nav";
import AppSidebar from "./AppSidebar.vue";
import AppMobileNav from "./AppMobileNav.vue";

async function routerAt(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: NAV_ITEMS.map((item) => ({ path: item.to, name: item.name, component: { template: "<div />" } })),
  });
  await router.push(path);
  await router.isReady();
  return router;
}

describe("AppSidebar", () => {
  it("renders a labelled primary nav with one link per route, marking the current one", async () => {
    const router = await routerAt("/liquidity");
    const wrapper = mount(AppSidebar, { global: { plugins: [router] } });
    expect(wrapper.attributes("data-testid")).toBe("shell.sidebar");
    expect(wrapper.get("nav").attributes("aria-label")).toBe("Primary");
    const links = wrapper.findAll("nav a");
    expect(links.map((a) => a.attributes("data-testid"))).toEqual(NAV_ITEMS.map((i) => `shell.nav.${i.name}`));
    expect(links.map((a) => a.attributes("href"))).toEqual(NAV_ITEMS.map((i) => i.to));
    expect(links.map((a) => a.attributes("aria-current"))).toEqual([undefined, undefined, undefined, undefined, "page", undefined]);
    expect(wrapper.get('[data-part="active-indicator"]').attributes("style")).toContain("translateY(192px)");
  });

  it("keeps labels for assistive tech when collapsed and emits the toggle", async () => {
    const router = await routerAt("/");
    const wrapper = mount(AppSidebar, { props: { collapsed: true }, global: { plugins: [router] } });
    expect(wrapper.attributes("data-collapsed")).toBe("true");
    const first = wrapper.get('[data-testid="shell.nav.home"]');
    expect(first.find("span.sr-only").text()).toBe("Dashboard");
    expect(first.attributes("title")).toBe("Dashboard");
    await wrapper.get('[data-testid="shell.sidebar-toggle"]').trigger("click");
    expect(wrapper.emitted("update:collapsed")).toEqual([[false]]);
    await wrapper.get('[data-testid="shell.sidebar.settings"]').trigger("click");
    expect(wrapper.emitted("openSettings")).toHaveLength(1);
  });

  it("uses tokens only", async () => {
    const router = await routerAt("/");
    expect(mount(AppSidebar, { global: { plugins: [router] } }).html()).not.toMatch(/\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/);
  });
});

describe("AppMobileNav", () => {
  it("is a second labelled primary nav with all six routes as stacked tabs", async () => {
    const router = await routerAt("/analyze");
    const wrapper = mount(AppMobileNav, { global: { plugins: [router] } });
    expect(wrapper.attributes("data-testid")).toBe("shell.mobile-nav");
    expect(wrapper.attributes("aria-label")).toBe("Primary");
    expect(wrapper.findAll("a")).toHaveLength(6);
    expect(wrapper.get('[data-testid="shell.nav.analyze"]').attributes("aria-current")).toBe("page");
    expect(wrapper.classes()).toContain("pb-safe-b");
  });
});
