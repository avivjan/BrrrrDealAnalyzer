// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";

import UiIconButton from "./UiIconButton.vue";

function mountIconButton(props: Record<string, unknown> = {}, attrs: Record<string, unknown> = {}) {
  return mount(UiIconButton, {
    props: { label: "Delete deal", ...props },
    attrs,
    slots: { default: '<i class="pi pi-trash" />' },
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("UiIconButton", () => {
  describe("the label", () => {
    it("becomes the button's accessible name", () => {
      expect(mountIconButton().attributes("aria-label")).toBe("Delete deal");
    });

    it("warns in dev when the label is empty", () => {
      const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
      mountIconButton({ label: "" });
      expect(warn).toHaveBeenCalledWith("[UiIconButton] label is required");
    });

    it("warns in dev when the label is omitted altogether", () => {
      const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
      mount(UiIconButton, { props: {} as { label: string } });
      expect(warn.mock.calls.flat()).toContain("[UiIconButton] label is required");
    });

    it("warns once per instance, not once per render", async () => {
      const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
      const wrapper = mountIconButton({ label: "" });
      await wrapper.setProps({ size: "md" });
      const ours = warn.mock.calls.filter(([first]) => first === "[UiIconButton] label is required");
      expect(ours).toHaveLength(1);
    });

    it("stays quiet when a label is given", () => {
      const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
      mountIconButton();
      expect(warn.mock.calls.flat()).not.toContain("[UiIconButton] label is required");
    });
  });

  describe("the element it renders", () => {
    it("renders a native button carrying its data-ui marker", () => {
      const button = mountIconButton().find("button");
      expect(button.exists()).toBe(true);
      expect(button.attributes("data-ui")).toBe("icon-button");
    });

    it('defaults type to "button"', () => {
      expect(mountIconButton().attributes("type")).toBe("button");
    });

    it("renders the icon passed in the default slot", () => {
      expect(mountIconButton().find("i.pi-trash").exists()).toBe(true);
    });

    it("renders no text of its own", () => {
      expect(mountIconButton().text()).toBe("");
    });
  });

  describe("what the parent still controls", () => {
    it("forwards a click", async () => {
      const onClick = vi.fn();
      const wrapper = mountIconButton({}, { onClick });
      await wrapper.find("button").trigger("click");
      expect(onClick).toHaveBeenCalledTimes(1);
    });

    it("keeps a native disabled attribute, and a disabled click does nothing", async () => {
      const onClick = vi.fn();
      const wrapper = mountIconButton({}, { disabled: true, onClick });
      expect(wrapper.find("button").attributes("disabled")).toBeDefined();
      await wrapper.find("button").trigger("click");
      expect(onClick).not.toHaveBeenCalled();
    });

    it("passes a data-testid through", () => {
      expect(mountIconButton({}, { "data-testid": "deal.delete" }).attributes("data-testid")).toBe(
        "deal.delete",
      );
    });

    it("lets an explicit aria-label win over the prop", () => {
      expect(mountIconButton({}, { "aria-label": "Remove" }).attributes("aria-label")).toBe("Remove");
    });
  });

  describe("the classes it composes", () => {
    it("is 32px square at sm and 40px square at md", () => {
      expect(mountIconButton().classes()).toEqual(expect.arrayContaining(["h-8", "w-8"]));
      expect(mountIconButton({ size: "md" }).classes()).toEqual(
        expect.arrayContaining(["h-10", "w-10"]),
      );
    });

    it("grows each size to a 44px hit area with a pseudo-element", () => {
      // 32 + 2x6 = 44, and 40 + 2x2 = 44.
      const sm = mountIconButton().classes();
      expect(sm).toContain("relative");
      expect(sm).toContain("before:absolute");
      expect(sm).toContain("before:-inset-1.5");
      expect(mountIconButton({ size: "md" }).classes()).toContain("before:-inset-0.5");
    });

    it("gives every variant its own look, from tokens only", () => {
      const variants = ["ghost", "secondary", "danger"] as const;
      const seen = variants.map((variant) => mountIconButton({ variant }).classes().join(" "));
      expect(new Set(seen).size).toBe(3);
      expect(seen[2]).toContain("text-negative");
      expect(seen.join(" ")).not.toMatch(/\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/);
    });

    it("keeps a keyboard focus ring", () => {
      expect(mountIconButton().classes()).toContain("focus-visible:ring-ring");
    });

    it("lets a caller's class override its own through cn()", () => {
      const classes = mountIconButton({}, { class: "h-12" }).classes();
      expect(classes).toContain("h-12");
      expect(classes).not.toContain("h-8");
    });
  });
});
