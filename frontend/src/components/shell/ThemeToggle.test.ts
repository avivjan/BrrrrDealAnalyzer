// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import { applyTheme, resetThemeForTests, resolvedTheme } from "../../design/theme";
import ThemeToggle from "./ThemeToggle.vue";

beforeEach(() => {
  localStorage.clear();
  resetThemeForTests();
});

describe("ThemeToggle", () => {
  it("names its destination and flips the mode", async () => {
    applyTheme("dark");
    const wrapper = mount(ThemeToggle);
    expect(wrapper.attributes("data-testid")).toBe("shell.theme-toggle");
    expect(wrapper.attributes("aria-label")).toBe("Switch to light mode");
    await wrapper.trigger("click");
    expect(resolvedTheme.value).toBe("light");
    expect(wrapper.attributes("aria-label")).toBe("Switch to dark mode");
    expect(localStorage.getItem("bw.theme")).toBe("light");
  });
});
