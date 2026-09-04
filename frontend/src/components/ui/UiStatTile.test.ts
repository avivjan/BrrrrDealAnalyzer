// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import UiStatTile from "./UiStatTile.vue";

function mountTile(
  props: Record<string, unknown> = {},
  slots: Record<string, string> = { default: "$1,240" },
  attrs: Record<string, unknown> = {},
) {
  return mount(UiStatTile, { props, slots, attrs });
}

describe("UiStatTile", () => {
  describe("the element it renders", () => {
    it("is a div carrying its data-ui marker", () => {
      const wrapper = mountTile();
      expect(wrapper.element.tagName).toBe("DIV");
      expect(wrapper.attributes("data-ui")).toBe("stat-tile");
    });

    it("sits on the muted card surface", () => {
      const classes = mountTile().classes();
      expect(classes).toContain("rounded-card");
      expect(classes).toContain("bg-surface-muted");
      expect(classes).toContain("p-3");
    });
  });

  describe("the value", () => {
    it("renders the default slot inside the value part", () => {
      expect(mountTile().find('[data-part="value"]').text()).toBe("$1,240");
    });

    it("uses tabular figures so digits do not jump as they change", () => {
      expect(mountTile().find('[data-part="value"]').classes()).toContain("tabular");
    });

    it("scales the value with size", () => {
      const sm = mountTile({ size: "sm" }).find('[data-part="value"]').classes();
      const md = mountTile({ size: "md" }).find('[data-part="value"]').classes();
      expect(sm).not.toEqual(md);
    });
  });

  describe("the label and the hint", () => {
    it("renders the label slot", () => {
      const wrapper = mountTile({}, { default: "$1,240", label: "Monthly cash flow" });
      expect(wrapper.find('[data-part="label"]').text()).toBe("Monthly cash flow");
    });

    it("falls back to the label prop when no slot is given", () => {
      expect(mountTile({ label: "Cap rate" }).find('[data-part="label"]').text()).toBe("Cap rate");
    });

    it("prefers the slot over the prop", () => {
      const wrapper = mountTile({ label: "Prop" }, { default: "$1,240", label: "Slot" });
      expect(wrapper.find('[data-part="label"]').text()).toBe("Slot");
    });

    it("renders no label region when neither is given", () => {
      expect(mountTile().find('[data-part="label"]').exists()).toBe(false);
    });

    it("renders the hint slot, and nothing when it is absent", () => {
      const wrapper = mountTile({}, { default: "$1,240", hint: "after debt service" });
      expect(wrapper.find('[data-part="hint"]').text()).toBe("after debt service");
      expect(mountTile().find('[data-part="hint"]').exists()).toBe(false);
    });
  });

  describe("tone, which must never be colour alone", () => {
    const ICONS = {
      positive: "pi-arrow-up",
      negative: "pi-arrow-down",
      warning: "pi-exclamation-triangle",
    } as const;

    for (const [tone, icon] of Object.entries(ICONS)) {
      it(`marks ${tone} with the ${icon} icon and a visually hidden word`, () => {
        const wrapper = mountTile({ tone });
        expect(wrapper.find("i").classes()).toEqual(expect.arrayContaining(["pi", icon]));
        expect(wrapper.find("i").attributes("aria-hidden")).toBe("true");
        expect(wrapper.find(".sr-only").text()).toBe(tone);
      });
    }

    it("colours the value with the tone", () => {
      expect(mountTile({ tone: "positive" }).find('[data-part="value"]').classes()).toContain(
        "text-positive",
      );
      expect(mountTile({ tone: "negative" }).find('[data-part="value"]').classes()).toContain(
        "text-negative",
      );
      expect(mountTile({ tone: "warning" }).find('[data-part="value"]').classes()).toContain(
        "text-warning",
      );
    });

    it("gives neutral neither an icon nor a hidden word", () => {
      const wrapper = mountTile();
      expect(wrapper.find("i").exists()).toBe(false);
      expect(wrapper.find(".sr-only").exists()).toBe(false);
      expect(wrapper.text()).toBe("$1,240");
    });

    it("uses tokens only, never palette literals", () => {
      const tones = ["neutral", "positive", "negative", "warning"] as const;
      const seen = tones.map((tone) => mountTile({ tone }).html());
      expect(seen.join(" ")).not.toMatch(/\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/);
    });
  });

  describe("what the parent still controls", () => {
    it("passes data-* and aria-* through to the root", () => {
      const wrapper = mountTile({}, { default: "$1,240" }, { "data-testid": "stats.cashflow" });
      expect(wrapper.attributes("data-testid")).toBe("stats.cashflow");
    });

    it("lets a caller's class override its own through cn()", () => {
      const classes = mountTile({}, { default: "$1,240" }, { class: "rounded-none" }).classes();
      expect(classes).toContain("rounded-none");
      expect(classes).not.toContain("rounded-card");
    });
  });
});
