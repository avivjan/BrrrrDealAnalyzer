// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import UiStepper from "./UiStepper.vue";

/**
 * jsdom has no media queries, so the `md:` responsive split can't be
 * exercised by mounting — it's checked against the raw source instead (see
 * `tokens.test.ts` for the same pattern). Built from plain strings, not a
 * `URL` instance: this test's environment is `jsdom`, so the global `URL` is
 * jsdom's WHATWG implementation, not Node's — `fs` rejects it.
 */
const source = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "UiStepper.vue"), "utf8");

const STEPS =
  '<li data-step="done">Buy</li><li data-step="active">Rehab</li><li data-step="todo">Rent</li>';

const SEVEN_STEPS = Array.from(
  { length: 7 },
  (_, i) => `<li data-step="todo">Stage ${i + 1}</li>`,
).join("");

function mountStepper(
  props: { count: number; compact?: boolean } = { count: 3 },
  slots: Record<string, string> = { default: STEPS },
  attrs: Record<string, unknown> = {},
) {
  return mount(UiStepper, { props, slots, attrs });
}

describe("UiStepper", () => {
  describe("what it announces", () => {
    it("is an ordered list, and says so even with its markers removed", () => {
      const wrapper = mountStepper();
      expect(wrapper.element.tagName).toBe("OL");
      expect(wrapper.attributes("role")).toBe("list");
      expect(wrapper.attributes("data-ui")).toBe("stepper");
    });
  });

  describe("the grid it lays the steps on", () => {
    it("publishes the step count as a custom property", () => {
      expect(mountStepper({ count: 4 }).attributes("style")).toContain("--steps: 4");
    });

    it("splits the row into equal columns driven by that property, at md: and up", () => {
      expect(mountStepper().classes().join(" ")).toContain(
        "md:grid-cols-[repeat(var(--steps),minmax(0,1fr))]",
      );
    });
  });

  describe("wrapping below md", () => {
    it("lays a 7-step pipeline on a wrapping, auto-fit track by default", () => {
      const wrapper = mountStepper({ count: 7 }, { default: SEVEN_STEPS });
      expect(wrapper.findAll("li")).toHaveLength(7);
      expect(wrapper.classes().join(" ")).toContain(
        "grid-cols-[repeat(auto-fit,minmax(6rem,1fr))]",
      );
    });

    it("keeps the single-row track as an md: override, not the default", () => {
      const classes = mountStepper().classes();
      expect(classes).not.toContain("grid-cols-[repeat(var(--steps),minmax(0,1fr))]");
    });

    it("clamps a wrapped label to two lines instead of ellipsising it to one", () => {
      expect(source).toMatch(/-webkit-line-clamp:\s*2/);
      expect(source).toMatch(/-webkit-box-orient:\s*vertical/);
      expect(source).toMatch(/overflow-wrap:\s*anywhere/);
    });

    it("keeps the single-row nowrap + ellipsis behaviour gated to md: and up", () => {
      const mdBlock = source.slice(source.indexOf("@media (min-width: 768px)"));
      expect(mdBlock).toMatch(/white-space:\s*nowrap/);
      expect(mdBlock).toMatch(/text-overflow:\s*ellipsis/);
      expect(source.slice(0, source.indexOf("@media (min-width: 768px)"))).not.toMatch(
        /white-space:\s*nowrap/,
      );
    });

    it("drops the connector below md and restores it at md: and up", () => {
      const beforeMd = source.slice(
        source.indexOf(":slotted([data-step])::before"),
        source.indexOf("@media (min-width: 768px)"),
      );
      expect(beforeMd).toMatch(/content:\s*none/);

      const mdBlock = source.slice(source.indexOf("@media (min-width: 768px)"));
      expect(mdBlock).toMatch(/content:\s*"";/);
    });
  });

  describe("what it holds", () => {
    it("renders the steps the caller passes, untouched", () => {
      const steps = mountStepper().findAll("li");
      expect(steps).toHaveLength(3);
      expect(steps.map((step) => step.attributes("data-step"))).toEqual([
        "done",
        "active",
        "todo",
      ]);
    });

    it("hard-codes no copy of its own", () => {
      expect(mountStepper().text()).toBe("BuyRehabRent");
    });
  });

  describe("presentation", () => {
    it("tightens the type when compact", () => {
      expect(mountStepper({ count: 3, compact: true }).classes()).not.toEqual(
        mountStepper().classes(),
      );
      expect(mountStepper({ count: 3, compact: true }).attributes("data-compact")).toBe("true");
      expect(mountStepper().attributes("data-compact")).toBeUndefined();
    });

    it("uses tokens for every colour it sets", () => {
      expect(mountStepper().html()).not.toMatch(
        /\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/,
      );
    });

    it("passes attrs through to the root and merges class through cn()", () => {
      const wrapper = mountStepper(
        { count: 3 },
        { default: STEPS },
        { "data-testid": "deal.steps", class: "mt-4" },
      );
      expect(wrapper.attributes("data-testid")).toBe("deal.steps");
      expect(wrapper.classes()).toContain("mt-4");
    });
  });
});
