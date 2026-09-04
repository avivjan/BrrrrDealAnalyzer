// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import UiBadge from "./UiBadge.vue";

function mountBadge(props: Record<string, unknown> = {}, slot = "Active") {
  return mount(UiBadge, { props, slots: { default: slot } });
}

describe("UiBadge", () => {
  describe("the element it renders", () => {
    it("is a span carrying its data-ui marker", () => {
      const wrapper = mountBadge();
      expect(wrapper.element.tagName).toBe("SPAN");
      expect(wrapper.attributes("data-ui")).toBe("badge");
    });

    it("is a pill: inline-flex, fully rounded, medium weight", () => {
      const classes = mountBadge().classes();
      expect(classes).toContain("inline-flex");
      expect(classes).toContain("rounded-full");
      expect(classes).toContain("font-medium");
      expect(classes).toContain("text-xs");
    });
  });

  describe("the copy", () => {
    it("renders exactly the slot text and nothing else", () => {
      expect(mountBadge({}, "Under contract").text()).toBe("Under contract");
    });

    it("adds no text of its own for a deal type — the icon is silent", () => {
      expect(mountBadge({ dealType: "BRRRR" }, "BRRRR").text()).toBe("BRRRR");
      expect(mountBadge({ dealType: "FLIP" }, "Flip").text()).toBe("Flip");
    });
  });

  describe("the deal type", () => {
    it("prepends a house for BRRRR and a dollar for FLIP", () => {
      const brrrr = mountBadge({ dealType: "BRRRR" }, "BRRRR").find("i");
      expect(brrrr.classes()).toEqual(expect.arrayContaining(["pi", "pi-home"]));
      const flip = mountBadge({ dealType: "FLIP" }, "Flip").find("i");
      expect(flip.classes()).toEqual(expect.arrayContaining(["pi", "pi-dollar"]));
    });

    it("hides the icon from assistive tech", () => {
      expect(mountBadge({ dealType: "BRRRR" }, "BRRRR").find("i").attributes("aria-hidden")).toBe(
        "true",
      );
    });

    it("renders no icon without a deal type", () => {
      expect(mountBadge().find("i").exists()).toBe(false);
    });

    it("sets the tone: BRRRR is the accent, FLIP is the warning family", () => {
      expect(mountBadge({ dealType: "BRRRR" }, "BRRRR").classes().join(" ")).toContain(
        "text-primary",
      );
      expect(mountBadge({ dealType: "FLIP" }, "Flip").classes().join(" ")).toContain("text-warning");
    });

    it("wins over an explicit tone, so the two can never disagree", () => {
      const classes = mountBadge({ dealType: "FLIP", tone: "negative" }, "Flip").classes().join(" ");
      expect(classes).toContain("text-warning");
      expect(classes).not.toContain("text-negative");
    });
  });

  describe("the classes it composes", () => {
    it("gives every tone its own look, from tokens only", () => {
      const tones = ["neutral", "primary", "positive", "negative", "warning", "info"] as const;
      const seen = tones.map((tone) => mountBadge({ tone }).classes().join(" "));
      expect(new Set(seen).size).toBe(6);
      expect(seen[1]).toContain("text-primary");
      expect(seen[2]).toContain("text-positive");
      expect(seen[3]).toContain("text-negative");
      expect(seen[4]).toContain("text-warning");
      expect(seen.join(" ")).not.toMatch(/\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/);
    });

    it("scales its type with size", () => {
      expect(mountBadge().classes()).toContain("text-xs");
      expect(mountBadge({ size: "md" }).classes()).toContain("text-sm");
      expect(mountBadge({ size: "md" }).classes()).not.toContain("text-xs");
    });
  });

  describe("what the parent still controls", () => {
    it("passes data-* and aria-* through to the root", () => {
      const wrapper = mount(UiBadge, {
        slots: { default: "Active" },
        attrs: { "data-testid": "deal.badge", "aria-label": "Deal status" },
      });
      expect(wrapper.attributes("data-testid")).toBe("deal.badge");
      expect(wrapper.attributes("aria-label")).toBe("Deal status");
    });

    it("lets a caller's class override its own through cn()", () => {
      const wrapper = mount(UiBadge, {
        slots: { default: "Active" },
        attrs: { class: "rounded-none" },
      });
      expect(wrapper.classes()).toContain("rounded-none");
      expect(wrapper.classes()).not.toContain("rounded-full");
    });
  });
});
