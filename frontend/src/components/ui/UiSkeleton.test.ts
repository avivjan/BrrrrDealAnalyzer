// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import UiSkeleton from "./UiSkeleton.vue";

function mountSkeleton(
  props: Record<string, unknown> = {},
  attrs: Record<string, unknown> = {},
) {
  return mount(UiSkeleton, { props, attrs });
}

describe("UiSkeleton", () => {
  describe("what it puts on screen", () => {
    it("draws one bar by default and one per line otherwise", () => {
      expect(mountSkeleton().findAll('[data-part="bar"]')).toHaveLength(1);
      expect(mountSkeleton({ lines: 3 }).findAll('[data-part="bar"]')).toHaveLength(3);
    });

    it("carries no text at all", () => {
      expect(mountSkeleton({ lines: 3 }).text()).toBe("");
    });

    it("shortens the last bar of a paragraph so it reads as prose", () => {
      const bars = mountSkeleton({ lines: 3 }).findAll('[data-part="bar"]');
      expect(bars[0]?.classes()).toContain("w-full");
      expect(bars[2]?.classes()).toContain("w-2/3");
      // A single bar fills its box: it is standing in for a shape, not a sentence.
      expect(mountSkeleton().get('[data-part="bar"]').classes()).not.toContain("w-2/3");
    });
  });

  describe("what it announces", () => {
    it("is hidden from assistive tech — it is scaffolding, not content", () => {
      expect(mountSkeleton().attributes("aria-hidden")).toBe("true");
      expect(mountSkeleton().attributes("data-ui")).toBe("skeleton");
    });
  });

  describe("presentation", () => {
    it("pulses, which the global reduced-motion rule neutralises", () => {
      expect(mountSkeleton().classes()).toContain("animate-pulse");
    });

    it("fills the bars from a token surface", () => {
      expect(mountSkeleton().get('[data-part="bar"]').classes()).toContain("bg-surface-muted");
      expect(mountSkeleton().html()).not.toMatch(
        /\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/,
      );
    });

    it("gives each radius its own rounding", () => {
      const radius = (rounded: string) =>
        mountSkeleton({ rounded }).get('[data-part="bar"]').classes();
      expect(radius("ctl")).toContain("rounded-ctl");
      expect(radius("card")).toContain("rounded-card");
      expect(radius("full")).toContain("rounded-full");
    });

    it("takes its size from the caller's classes on the root", () => {
      const wrapper = mountSkeleton({}, { class: "h-24 w-48", "data-testid": "deals.loading" });
      expect(wrapper.classes()).toContain("h-24");
      expect(wrapper.classes()).toContain("w-48");
      expect(wrapper.attributes("data-testid")).toBe("deals.loading");
    });
  });
});
