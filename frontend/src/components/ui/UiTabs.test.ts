// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import UiTabs from "./UiTabs.vue";

const TABS = '<button role="tab">BRRRR</button><button role="tab">Flip</button>';

function mountTabs(
  props: Record<string, unknown> = {},
  slots: Record<string, string> = { default: TABS },
  attrs: Record<string, unknown> = {},
) {
  return mount(UiTabs, { props, slots, attrs });
}

describe("UiTabs", () => {
  describe("what it announces", () => {
    it("is a tablist", () => {
      const wrapper = mountTabs();
      expect(wrapper.attributes("role")).toBe("tablist");
      expect(wrapper.attributes("data-ui")).toBe("tabs");
    });

    it("takes a name when the tabs are not otherwise labelled", () => {
      expect(mountTabs({ ariaLabel: "Deal type" }).attributes("aria-label")).toBe("Deal type");
      expect(mountTabs().attributes("aria-label")).toBeUndefined();
    });
  });

  describe("what it holds", () => {
    it("renders the tabs the caller passes, untouched", () => {
      const wrapper = mountTabs();
      const tabs = wrapper.findAll('[role="tab"]');
      expect(tabs).toHaveLength(2);
      expect(tabs.map((tab) => tab.text())).toEqual(["BRRRR", "Flip"]);
    });

    it("hard-codes no copy of its own", () => {
      expect(mountTabs().text()).toBe("BRRRRFlip");
    });
  });

  describe("presentation", () => {
    it("is an inset track that scrolls rather than wraps", () => {
      const classes = mountTabs().classes();
      expect(classes).toContain("inline-flex");
      expect(classes).toContain("rounded-ctl");
      expect(classes).toContain("bg-surface-muted");
      expect(classes).toContain("overflow-x-auto");
      expect(classes).toContain("p-1");
      expect(classes).toContain("gap-1");
    });

    it("uses tokens for every colour it sets", () => {
      expect(mountTabs().html()).not.toMatch(
        /\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/,
      );
    });

    it("passes attrs through to the root and merges class through cn()", () => {
      const wrapper = mountTabs({}, { default: TABS }, { "data-testid": "deal.tabs", class: "w-full" });
      expect(wrapper.attributes("data-testid")).toBe("deal.tabs");
      expect(wrapper.classes()).toContain("w-full");
    });
  });
});
