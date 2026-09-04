// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import UiSectionHeader from "./UiSectionHeader.vue";

function mountHeader(
  props: Record<string, unknown> = {},
  slots: Record<string, string> = {},
  attrs: Record<string, unknown> = {},
) {
  return mount(UiSectionHeader, { props, attrs, slots: { default: "My deals", ...slots } });
}

describe("UiSectionHeader", () => {
  describe("the heading", () => {
    it("is an h2 by default", () => {
      const wrapper = mountHeader();
      expect(wrapper.get('[data-part="title"]').element.tagName).toBe("H2");
      expect(wrapper.get('[data-part="title"]').text()).toBe("My deals");
    });

    it("renders whatever level `as` names", () => {
      const levels = ["h1", "h2", "h3", "h4"] as const;
      for (const as of levels) {
        expect(mountHeader({ as }).get('[data-part="title"]').element.tagName).toBe(
          as.toUpperCase(),
        );
      }
    });

    it("scales the type with the level", () => {
      const sizes = (["h1", "h2", "h3", "h4"] as const).map((as) =>
        mountHeader({ as }).get('[data-part="title"]').classes().join(" "),
      );
      expect(new Set(sizes).size).toBe(4);
    });
  });

  describe("the slots", () => {
    it("renders a subtitle only when one is given", () => {
      expect(mountHeader().find('[data-part="subtitle"]').exists()).toBe(false);
      const wrapper = mountHeader({}, { subtitle: "3 active" });
      expect(wrapper.get('[data-part="subtitle"]').text()).toBe("3 active");
      expect(wrapper.get('[data-part="subtitle"]').classes()).toContain("text-fg-muted");
    });

    it("renders actions only when they are given", () => {
      expect(mountHeader().find('[data-part="actions"]').exists()).toBe(false);
      expect(mountHeader({}, { actions: "<button>New</button>" }).get("button").text()).toBe("New");
    });

    it("hard-codes no copy of its own", () => {
      expect(mountHeader({}, { subtitle: "3 active" }).text()).toBe("My deals3 active");
    });
  });

  describe("presentation", () => {
    it("puts the actions opposite the title", () => {
      const classes = mountHeader().classes();
      expect(classes).toContain("flex");
      expect(classes).toContain("items-start");
      expect(classes).toContain("justify-between");
      expect(classes).toContain("gap-3");
    });

    it("uses tokens for every colour it sets", () => {
      const html = mountHeader({}, { subtitle: "3 active" }).html();
      expect(html).not.toMatch(/\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/);
    });

    it("passes attrs through to the root and merges class through cn()", () => {
      const wrapper = mountHeader({}, {}, { "data-testid": "deals.header", class: "mb-8" });
      expect(wrapper.attributes("data-ui")).toBe("section-header");
      expect(wrapper.attributes("data-testid")).toBe("deals.header");
      expect(wrapper.classes()).toContain("mb-8");
    });
  });
});
