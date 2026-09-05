// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { defineComponent, h, withModifiers } from "vue";
import { mount } from "@vue/test-utils";

import UiButton from "./UiButton.vue";

/**
 * `UiButton` is presentational: it owns no state and forwards everything. The
 * tests are therefore about the seam — what reaches the native `<button>` and
 * what the parent still controls — rather than about the class strings, which
 * Phase 3 is free to retune.
 */
function mountButton(props: Record<string, unknown> = {}, attrs: Record<string, unknown> = {}) {
  return mount(UiButton, { props, attrs, slots: { default: "Analyze" } });
}

describe("UiButton", () => {
  describe("the element it renders", () => {
    it("renders a native button carrying its data-ui marker", () => {
      const button = mountButton().find("button");
      expect(button.exists()).toBe(true);
      expect(button.attributes("data-ui")).toBe("button");
    });

    it("renders the default slot", () => {
      expect(mountButton().text()).toBe("Analyze");
    });

    it('defaults type to "button" so it never submits a form by accident', () => {
      expect(mountButton().attributes("type")).toBe("button");
    });

    it("uses the type it is given", () => {
      expect(mountButton({ type: "submit" }).attributes("type")).toBe("submit");
    });
  });

  describe("what the parent still controls", () => {
    it("forwards a click to the parent's handler", async () => {
      const onClick = vi.fn();
      const wrapper = mountButton({}, { onClick });
      await wrapper.find("button").trigger("click");
      expect(onClick).toHaveBeenCalledTimes(1);
    });

    it("honours @click.stop: an outer handler does not fire", async () => {
      const onParent = vi.fn();
      const onChild = vi.fn();
      const Wrapper = defineComponent({
        setup: () => () =>
          h("div", { onClick: onParent }, [
            h(UiButton, { onClick: withModifiers(onChild, ["stop"]) }, () => "Go"),
          ]),
      });
      const wrapper = mount(Wrapper);
      await wrapper.find("button").trigger("click");
      expect(onChild).toHaveBeenCalledTimes(1);
      expect(onParent).not.toHaveBeenCalled();
    });

    it("passes a data-testid straight through to the button", () => {
      const wrapper = mountButton({}, { "data-testid": "deal.analyze" });
      expect(wrapper.find("button").attributes("data-testid")).toBe("deal.analyze");
    });

    it("passes aria-* attributes through", () => {
      expect(mountButton({}, { "aria-label": "Analyze deal" }).attributes("aria-label")).toBe(
        "Analyze deal",
      );
    });

    it("keeps the parent's disabled attribute, and a disabled click does nothing", async () => {
      const onClick = vi.fn();
      const wrapper = mountButton({}, { disabled: true, onClick });
      expect(wrapper.find("button").attributes("disabled")).toBeDefined();
      await wrapper.find("button").trigger("click");
      expect(onClick).not.toHaveBeenCalled();
    });
  });

  describe("loading", () => {
    it("renders a spinner, hidden from assistive tech", () => {
      const spinner = mountButton({ loading: true }).find(".pi-spinner");
      expect(spinner.exists()).toBe(true);
      expect(spinner.classes()).toContain("pi-spin");
      expect(spinner.attributes("aria-hidden")).toBe("true");
    });

    it('announces the wait with aria-busy="true"', () => {
      expect(mountButton({ loading: true }).attributes("aria-busy")).toBe("true");
    });

    it("does not disable the button — the parent owns that decision", async () => {
      const onClick = vi.fn();
      const wrapper = mountButton({ loading: true }, { onClick });
      expect(wrapper.find("button").attributes("disabled")).toBeUndefined();
      await wrapper.find("button").trigger("click");
      expect(onClick).toHaveBeenCalledTimes(1);
    });

    it("renders neither spinner nor aria-busy when idle", () => {
      const wrapper = mountButton();
      expect(wrapper.find(".pi-spinner").exists()).toBe(false);
      expect(wrapper.attributes("aria-busy")).toBeUndefined();
    });
  });

  describe("the tab variant", () => {
    it('reports aria-selected="true" and role="tab" when active', () => {
      const wrapper = mountButton({ variant: "tab", active: true });
      expect(wrapper.attributes("aria-selected")).toBe("true");
      expect(wrapper.attributes("role")).toBe("tab");
    });

    it('reports aria-selected="false" when inactive', () => {
      expect(mountButton({ variant: "tab" }).attributes("aria-selected")).toBe("false");
    });

    it("styles the active tab differently from the inactive one", () => {
      const active = mountButton({ variant: "tab", active: true }).classes();
      const inactive = mountButton({ variant: "tab" }).classes();
      expect(active).not.toEqual(inactive);
    });

    it("lets an explicit role attribute win", () => {
      expect(mountButton({ variant: "tab" }, { role: "switch" }).attributes("role")).toBe("switch");
    });

    it("adds neither role nor aria-selected to a non-tab variant", () => {
      const wrapper = mountButton({ variant: "primary", active: true });
      expect(wrapper.attributes("role")).toBeUndefined();
      expect(wrapper.attributes("aria-selected")).toBeUndefined();
    });
  });

  describe("the classes it composes", () => {
    it("uses semantic tokens rather than palette literals", () => {
      const classes = mountButton().classes().join(" ");
      expect(classes).toContain("bg-primary");
      expect(classes).toContain("text-primary-fg");
      expect(classes).not.toMatch(/\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/);
    });

    it("gives every variant its own look", () => {
      const variants = ["primary", "secondary", "ghost", "danger", "brrrr", "flip", "tab"] as const;
      const seen = variants.map((variant) => mountButton({ variant }).classes().join(" "));
      expect(new Set(seen).size).toBeGreaterThan(1);
      expect(seen[3]).toContain("bg-negative");
      expect(seen[5]).toContain("bg-warning");
    });

    it("gives each size its own minimum height", () => {
      expect(mountButton({ size: "sm" }).classes()).toContain("min-h-6");
      expect(mountButton().classes()).toContain("min-h-11");
      expect(mountButton({ size: "lg" }).classes()).toContain("min-h-12");
    });

    it("fills its container only when block is set", () => {
      expect(mountButton({ block: true }).classes()).toContain("w-full");
      expect(mountButton().classes()).not.toContain("w-full");
    });

    it("keeps a keyboard focus ring", () => {
      expect(mountButton().classes()).toContain("focus-visible:ring-ring");
    });

    it("lets a caller's class override its own through cn()", () => {
      const classes = mountButton({}, { class: "rounded-full" }).classes();
      expect(classes).toContain("rounded-full");
      expect(classes).not.toContain("rounded-ctl");
    });
  });
});
