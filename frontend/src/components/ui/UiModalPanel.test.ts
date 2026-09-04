// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";

import UiModalPanel from "./UiModalPanel.vue";

function mountPanel(
  props: Record<string, unknown> = {},
  slots: Record<string, string> = {},
  attrs: Record<string, unknown> = {},
) {
  return mount(UiModalPanel, {
    props,
    attrs,
    slots: { header: "Edit deal", default: "Body", ...slots },
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("UiModalPanel", () => {
  describe("what it announces", () => {
    it("is a modal dialog", () => {
      const wrapper = mountPanel();
      expect(wrapper.attributes("role")).toBe("dialog");
      expect(wrapper.attributes("aria-modal")).toBe("true");
      expect(wrapper.attributes("data-ui")).toBe("modal-panel");
    });

    it("names itself with the heading it renders around the header slot", () => {
      const wrapper = mountPanel();
      const heading = wrapper.get("h2");
      expect(heading.text()).toBe("Edit deal");
      expect(wrapper.attributes("aria-labelledby")).toBe(heading.attributes("id"));
      expect(heading.attributes("id")).toBeTruthy();
    });

    it("defers to an explicit labelledBy and renders no heading of its own", () => {
      const wrapper = mountPanel({ labelledBy: "deal-title" });
      expect(wrapper.attributes("aria-labelledby")).toBe("deal-title");
      expect(wrapper.find("h2").exists()).toBe(false);
      expect(wrapper.get('[data-part="header"]').text()).toBe("Edit deal");
    });

    it("claims no name at all when there is no header and no labelledBy", () => {
      const wrapper = mount(UiModalPanel, { slots: { default: "Body" } });
      expect(wrapper.attributes("aria-labelledby")).toBeUndefined();
      expect(wrapper.find('[data-part="header"]').exists()).toBe(false);
    });
  });

  describe("the regions", () => {
    it("renders the body in a scroll container that does not chain", () => {
      const body = mountPanel().get('[data-part="body"]');
      expect(body.text()).toBe("Body");
      expect(body.classes()).toContain("overscroll-contain");
      expect(body.classes()).toContain("overflow-y-auto");
      expect(body.classes()).toContain("custom-scrollbar");
      expect(body.classes()).toContain("min-h-0");
    });

    it("divides header and footer from the body with token rules", () => {
      const wrapper = mountPanel({}, { footer: "Save" });
      expect(wrapper.get('[data-part="header"]').classes()).toContain("border-b");
      expect(wrapper.get('[data-part="header"]').classes()).toContain("border-line");
      expect(wrapper.get('[data-part="footer"]').classes()).toContain("border-t");
    });

    it("pads the footer past the home indicator", () => {
      const footer = mountPanel({}, { footer: "Save" }).get('[data-part="footer"]');
      expect(footer.classes()).toContain("pb-safe-b");
    });

    it("renders no footer region unless the slot is passed", () => {
      expect(mountPanel().find('[data-part="footer"]').exists()).toBe(false);
    });

    it("hard-codes no copy of its own", () => {
      expect(mountPanel({}, { footer: "Save" }).text()).toBe("Edit dealBodySave");
    });
  });

  describe("its shape", () => {
    it("gives every size its own width", () => {
      const sizes = ["sm", "md", "lg", "xl", "full"] as const;
      const seen = sizes.map((size) => mountPanel({ size }).classes().join(" "));
      expect(new Set(seen).size).toBe(5);
      expect(seen[1]).toContain("max-w-lg");
      expect(seen[2]).toContain("max-w-3xl");
      expect(seen[3]).toContain("max-w-5xl");
    });

    it("fills the phone screen at size full and returns to a panel on desktop", () => {
      const classes = mountPanel({ size: "full" }).classes();
      expect(classes).toContain("h-[100svh]");
      expect(classes).toContain("md:h-auto");
      expect(classes).not.toContain("max-h-[90svh]");
      expect(classes).toContain("md:max-h-[90svh]");
      expect(classes).toContain("rounded-none");
      expect(classes).not.toContain("rounded-panel");
      expect(classes).toContain("md:rounded-panel");
    });

    it("sits on token surface and elevation and never exceeds the viewport", () => {
      const classes = mountPanel().classes();
      expect(classes).toContain("bg-surface");
      expect(classes).toContain("shadow-3");
      expect(classes).toContain("rounded-panel");
      expect(classes).toContain("max-h-[90svh]");
      expect(classes).toContain("flex");
    });

    it("uses tokens for every colour it sets", () => {
      const html = mountPanel({}, { footer: "Save" }).html();
      expect(html).not.toMatch(/\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/);
    });
  });

  describe("the behaviour it deliberately does not own", () => {
    it("registers no document or window listener", () => {
      const onDocument = vi.spyOn(document, "addEventListener");
      const onWindow = vi.spyOn(window, "addEventListener");
      const wrapper = mountPanel();
      expect(onDocument).not.toHaveBeenCalled();
      expect(onWindow).not.toHaveBeenCalled();
      wrapper.unmount();
    });

    it("lets a click inside reach the parent's handler exactly once", async () => {
      const onClick = vi.fn();
      const wrapper = mountPanel({}, { footer: "Save" }, { onClick });
      await wrapper.get('[data-part="body"]').trigger("click");
      await wrapper.get('[data-part="footer"]').trigger("click");
      // Twice, not four times: the panel forwards nothing and re-emits nothing,
      // so each click reaches the parent exactly once, by bubbling.
      expect(onClick).toHaveBeenCalledTimes(2);
    });

    it("declares no events of its own", () => {
      expect((UiModalPanel as unknown as { emits?: unknown }).emits).toBeUndefined();
    });

    it("passes attrs through to the root and merges class through cn()", () => {
      const wrapper = mountPanel({}, {}, { "data-testid": "deal.modal", class: "rounded-none" });
      expect(wrapper.attributes("data-testid")).toBe("deal.modal");
      expect(wrapper.classes()).toContain("rounded-none");
      expect(wrapper.classes()).not.toContain("rounded-panel");
    });

    it("lets an explicit role override the default", () => {
      expect(mountPanel({}, {}, { role: "alertdialog" }).attributes("role")).toBe("alertdialog");
    });
  });
});
