// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import UiEmptyState from "./UiEmptyState.vue";

function mountEmpty(
  props: Record<string, unknown> = {},
  slots: Record<string, string> = {},
  attrs: Record<string, unknown> = {},
) {
  return mount(UiEmptyState, { props, attrs, slots: { default: "No deals yet", ...slots } });
}

describe("UiEmptyState", () => {
  describe("the icon", () => {
    it("renders the primeicon it is given, hidden from assistive tech", () => {
      const icon = mountEmpty({ icon: "pi pi-inbox" }).get("i");
      expect(icon.classes()).toContain("pi-inbox");
      expect(icon.attributes("aria-hidden")).toBe("true");
    });

    it("renders no icon element when none is named", () => {
      expect(mountEmpty().find("i").exists()).toBe(false);
    });
  });

  describe("the slots", () => {
    it("renders the default slot as the title", () => {
      expect(mountEmpty().get('[data-part="title"]').text()).toBe("No deals yet");
    });

    it("renders a description only when one is given", () => {
      expect(mountEmpty().find('[data-part="description"]').exists()).toBe(false);
      expect(mountEmpty({}, { description: "Add one to start" }).text()).toContain(
        "Add one to start",
      );
    });

    it("renders actions only when they are given", () => {
      expect(mountEmpty().find('[data-part="actions"]').exists()).toBe(false);
      expect(mountEmpty({}, { actions: "<button>Add deal</button>" }).get("button").text()).toBe(
        "Add deal",
      );
    });

    it("hard-codes no copy of its own", () => {
      expect(mountEmpty({ icon: "pi pi-inbox" }, { description: "Add one" }).text()).toBe(
        "No deals yetAdd one",
      );
    });
  });

  describe("presentation", () => {
    it("is a centred dashed placeholder in muted ink", () => {
      const classes = mountEmpty().classes();
      expect(classes).toContain("rounded-card");
      expect(classes).toContain("border-dashed");
      expect(classes).toContain("border-line");
      expect(classes).toContain("text-center");
      expect(classes).toContain("text-fg-muted");
    });

    it("uses tokens for every colour it sets", () => {
      const html = mountEmpty({ icon: "pi pi-inbox" }, { description: "Add one" }).html();
      expect(html).not.toMatch(/\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/);
    });

    it("passes attrs through to the root and merges class through cn()", () => {
      const wrapper = mountEmpty({}, {}, { "data-testid": "deals.empty", class: "border-solid" });
      expect(wrapper.attributes("data-ui")).toBe("empty-state");
      expect(wrapper.attributes("data-testid")).toBe("deals.empty");
      expect(wrapper.classes()).toContain("border-solid");
      expect(wrapper.classes()).not.toContain("border-dashed");
    });
  });
});
