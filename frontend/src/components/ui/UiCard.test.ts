// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";

import UiCard from "./UiCard.vue";

function mountCard(
  props: Record<string, unknown> = {},
  slots: Record<string, string> = { default: "Body" },
  attrs: Record<string, unknown> = {},
) {
  return mount(UiCard, { props, slots, attrs });
}

describe("UiCard", () => {
  describe("the element it renders", () => {
    it("is a div carrying its data-ui marker by default", () => {
      const wrapper = mountCard();
      expect(wrapper.element.tagName).toBe("DIV");
      expect(wrapper.attributes("data-ui")).toBe("card");
    });

    it("renders whatever tag `as` names", () => {
      expect(mountCard({ as: "section" }).element.tagName).toBe("SECTION");
      expect(mountCard({ as: "li" }).element.tagName).toBe("LI");
    });
  });

  describe("the slots", () => {
    it("renders the default slot as the body", () => {
      expect(mountCard().find('[data-part="body"]').text()).toBe("Body");
    });

    it("renders a header and a footer when they are given", () => {
      const wrapper = mountCard({}, { default: "Body", header: "Title", footer: "Actions" });
      expect(wrapper.find('[data-part="header"]').text()).toBe("Title");
      expect(wrapper.find('[data-part="footer"]').text()).toBe("Actions");
    });

    it("renders no header or footer region when neither slot is passed", () => {
      const wrapper = mountCard();
      expect(wrapper.find('[data-part="header"]').exists()).toBe(false);
      expect(wrapper.find('[data-part="footer"]').exists()).toBe(false);
    });

    it("renders no body region when the default slot is empty", () => {
      const wrapper = mountCard({}, { header: "Title" });
      expect(wrapper.find('[data-part="body"]').exists()).toBe(false);
    });

    it("hard-codes no copy of its own", () => {
      expect(mountCard({}, { default: "Body" }).text()).toBe("Body");
    });
  });

  describe("the classes it composes", () => {
    it("gives every tone its own surface, from tokens only", () => {
      const tones = ["surface", "muted", "elevated"] as const;
      const seen = tones.map((tone) => mountCard({ tone }).classes().join(" "));
      expect(new Set(seen).size).toBe(3);
      expect(seen[0]).toContain("bg-surface");
      expect(seen[1]).toContain("bg-surface-muted");
      expect(seen[2]).toContain("shadow-2");
      expect(seen.join(" ")).not.toMatch(/\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/);
    });

    it("carries the card radius and a token border", () => {
      const classes = mountCard().classes();
      expect(classes).toContain("rounded-card");
      expect(classes).toContain("border-line");
    });

    it("adds lift and a pointer only when interactive", () => {
      const interactive = mountCard({ interactive: true }).classes();
      expect(interactive).toContain("hover:shadow-2");
      expect(interactive).toContain("cursor-pointer");
      expect(interactive).toContain("active:scale-[0.99]");
      expect(mountCard().classes()).not.toContain("cursor-pointer");
    });

    it("pads its regions by size, and not at all at none", () => {
      const pad = (padding: string) =>
        mountCard({ padding }).find('[data-part="body"]').classes().join(" ");
      expect(pad("sm")).toContain("p-3");
      expect(mountCard().find('[data-part="body"]').classes()).toContain("p-4");
      expect(pad("lg")).toContain("p-6");
      expect(pad("none")).not.toMatch(/\bp-\d/);
    });

    it("lets a caller's class override its own through cn()", () => {
      const classes = mountCard({}, { default: "Body" }, { class: "rounded-none" }).classes();
      expect(classes).toContain("rounded-none");
      expect(classes).not.toContain("rounded-card");
    });
  });

  describe("what the parent still controls", () => {
    it("fires the parent's click handler on the root", async () => {
      const onClick = vi.fn();
      const wrapper = mountCard({ interactive: true }, { default: "Body" }, { onClick });
      await wrapper.trigger("click");
      expect(onClick).toHaveBeenCalledTimes(1);
    });

    it("passes data-* and aria-* through to the root", () => {
      const wrapper = mountCard(
        {},
        { default: "Body" },
        { "data-testid": "deal.card", "aria-label": "Deal" },
      );
      expect(wrapper.attributes("data-testid")).toBe("deal.card");
      expect(wrapper.attributes("aria-label")).toBe("Deal");
    });
  });
});
