// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import UiSaveStatus from "./UiSaveStatus.vue";

function mountStatus(
  props: Record<string, unknown> = {},
  slots: Record<string, string> = { default: "Saved" },
  attrs: Record<string, unknown> = {},
) {
  return mount(UiSaveStatus, { props, slots, attrs });
}

describe("UiSaveStatus", () => {
  describe("what it announces", () => {
    it("is a polite live region", () => {
      const wrapper = mountStatus({ status: "saving" });
      expect(wrapper.attributes("role")).toBe("status");
      expect(wrapper.attributes("aria-live")).toBe("polite");
      expect(wrapper.attributes("data-ui")).toBe("save-status");
    });

    it("exposes the state for styling and for tests", () => {
      const states = ["idle", "saving", "saved", "error"] as const;
      for (const status of states) {
        expect(mountStatus({ status }).attributes("data-state")).toBe(status);
      }
    });
  });

  describe("the copy", () => {
    it("renders the caller's label, never one of its own", () => {
      expect(mountStatus({ status: "saved" }, { default: "All changes saved" }).text()).toBe(
        "All changes saved",
      );
      expect(mountStatus({ status: "error" }, { default: "Could not save" }).text()).toBe(
        "Could not save",
      );
    });

    it("says nothing at all when idle, even with a label in the slot", () => {
      expect(mountStatus({ status: "idle" }).text()).toBe("");
    });
  });

  describe("the icon", () => {
    it("spins while saving", () => {
      const icon = mountStatus({ status: "saving" }).get("i");
      expect(icon.classes()).toContain("pi-spinner");
      expect(icon.classes()).toContain("pi-spin");
      expect(icon.attributes("aria-hidden")).toBe("true");
    });

    it("ticks when saved and warns on an error", () => {
      expect(mountStatus({ status: "saved" }).get("i").classes()).toContain("pi-check");
      expect(mountStatus({ status: "error" }).get("i").classes()).toContain(
        "pi-exclamation-circle",
      );
    });

    it("shows no icon when idle", () => {
      expect(mountStatus({ status: "idle" }).find("i").exists()).toBe(false);
    });
  });

  describe("presentation", () => {
    it("keeps its box when idle so the row beside it never shifts", () => {
      const wrapper = mountStatus({ status: "idle" });
      expect(wrapper.element.tagName).toBe("SPAN");
      expect(wrapper.attributes("hidden")).toBeUndefined();
      expect(wrapper.classes()).toContain("inline-flex");
      // The reserved height is what stops a row reflowing as saving starts.
      expect(wrapper.classes()).toContain("min-h-4");
    });

    it("tones the saved and error states apart, from tokens only", () => {
      expect(mountStatus({ status: "saved" }).classes()).toContain("text-positive");
      expect(mountStatus({ status: "error" }).classes()).toContain("text-negative");
      expect(mountStatus({ status: "saving" }).classes()).toContain("text-fg-muted");
      expect(mountStatus({ status: "error" }).html()).not.toMatch(
        /\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/,
      );
    });

    it("passes attrs through to the root and merges class through cn()", () => {
      const wrapper = mountStatus(
        { status: "saved" },
        { default: "Saved" },
        { "data-testid": "deal.save", class: "ml-auto" },
      );
      expect(wrapper.attributes("data-testid")).toBe("deal.save");
      expect(wrapper.classes()).toContain("ml-auto");
    });
  });
});
