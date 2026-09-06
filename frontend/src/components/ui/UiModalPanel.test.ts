// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { h, nextTick, ref } from "vue";
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

    /**
     * Same regression as `UiField`'s: slots are not reactive, so a `computed`
     * over `slots.header` froze the dialog's name at its first render. A panel
     * whose header arrives with its data would have stayed anonymous.
     */
    it("names itself once a header slot arrives after mount", async () => {
      const showHeader = ref(false);
      const page = mount({
        render: () =>
          h(UiModalPanel, null, {
            default: () => "Body",
            ...(showHeader.value ? { header: () => "Edit deal" } : {}),
          }),
      });
      const panel = page.get('[data-ui="modal-panel"]');

      expect(panel.attributes("aria-labelledby")).toBeUndefined();

      showHeader.value = true;
      await nextTick();
      expect(panel.attributes("aria-labelledby")).toBe(page.get("h2").attributes("id"));

      showHeader.value = false;
      await nextTick();
      expect(panel.attributes("aria-labelledby")).toBeUndefined();
    });

    it("still lets an explicit labelledBy win over a late header", async () => {
      const showHeader = ref(false);
      const page = mount({
        render: () =>
          h(UiModalPanel, { labelledBy: "deal-title" }, {
            default: () => "Body",
            ...(showHeader.value ? { header: () => "Edit deal" } : {}),
          }),
      });

      showHeader.value = true;
      await nextTick();
      expect(page.get('[data-ui="modal-panel"]').attributes("aria-labelledby")).toBe("deal-title");
      expect(page.find("h2").exists()).toBe(false);
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

    /**
     * The four classes that turn "the content is too tall" into "the body
     * scrolls". They are a set: a capped `flex-col` panel, a body that may both
     * grow and shrink, and header and footer that refuse to. Drop `min-h-0` and
     * the body inherits a flex item's `min-height: auto`, so it declines to
     * shrink below its content, the panel's cap is exceeded instead, and the
     * scrollbar never appears. Drop `shrink-0` and the header and footer
     * collapse instead of the body scrolling.
     *
     * jsdom does no layout, so this is asserted as the contract rather than by
     * measuring; `e2e/checks/modal-scroll.spec.ts` measures the real thing in
     * four browsers.
     */
    it("gives the body the flex rules that let it shrink and scroll", () => {
      const wrapper = mountPanel({}, { footer: "Save" });

      expect(wrapper.classes()).toContain("flex");
      expect(wrapper.classes()).toContain("flex-col");
      expect(wrapper.classes()).toContain("max-h-[90svh]");

      const body = wrapper.get('[data-part="body"]');
      expect(body.classes()).toContain("flex-1");
      expect(body.classes()).toContain("min-h-0");

      expect(wrapper.get('[data-part="header"]').classes()).toContain("shrink-0");
      expect(wrapper.get('[data-part="footer"]').classes()).toContain("shrink-0");
    });

    /**
     * A modal has exactly one scroller. A second `overflow-y-auto` region
     * nested inside the body is the bug this contract exists to prevent: with
     * no height cap it can never scroll, and with `overscroll-contain` it stops
     * the gesture from reaching the body that can. Callers put content in the
     * default slot; the panel must not wrap it in another scroll port.
     */
    it("creates exactly one scroll container", () => {
      const wrapper = mountPanel({}, { footer: "Save" });
      const scrollPorts = wrapper
        .findAll("*")
        .filter((el) => el.classes().some((c) => c.startsWith("overflow-y-")));

      expect(scrollPorts).toHaveLength(1);
      expect(scrollPorts[0]!.attributes("data-part")).toBe("body");
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
