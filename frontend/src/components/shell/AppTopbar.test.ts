// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia } from "pinia";

import { resetThemeForTests } from "../../design/theme";
import AppTopbar from "./AppTopbar.vue";

describe("AppTopbar", () => {
  it("is the page header with the title as h1 and every shell control", async () => {
    resetThemeForTests();
    const wrapper = mount(AppTopbar, { props: { title: "Liquidity" }, global: { plugins: [createPinia()] } });
    expect(wrapper.element.tagName).toBe("HEADER");
    expect(wrapper.attributes("data-testid")).toBe("shell.topbar");
    expect(wrapper.get("h1").text()).toBe("Liquidity");
    for (const id of ["shell.command-trigger", "shell.theme-toggle", "shell.settings-open", "app.status"]) {
      expect(wrapper.find(`[data-testid="${id}"]`).exists(), id).toBe(true);
    }
    await wrapper.get('[data-testid="shell.settings-open"]').trigger("click");
    await wrapper.get('[data-testid="shell.command-trigger"]').trigger("click");
    await wrapper.get('[data-testid="shell.command-trigger-mobile"]').trigger("click");
    expect(wrapper.emitted("openSettings")).toHaveLength(1);
    expect(wrapper.emitted("openPalette")).toHaveLength(2);
  });
});
