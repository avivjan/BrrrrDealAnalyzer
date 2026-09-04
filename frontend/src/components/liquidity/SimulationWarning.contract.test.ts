// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { DOMWrapper, mount } from "@vue/test-utils";

import SimulationWarning from "./SimulationWarning.vue";
import type { SimulationResult } from "../../types/liquidity";

function result(overrides: Partial<SimulationResult> = {}): SimulationResult {
  return {
    min: -12.5,
    minDates: ["2026-05-01"],
    firstNegativeDate: "2026-04-20",
    negativeDates: ["2026-04-20", "2026-05-01"],
    breachesReserve: true,
    reserveBreachDates: ["2026-04-18"],
    ...overrides,
  };
}

/** Teleports to `<body>`. */
function mountWarning(props: {
  open?: boolean;
  result?: SimulationResult | null;
  severity?: "hard" | "soft" | "none";
}) {
  return mount(SimulationWarning, {
    props: {
      open: true,
      result: result(),
      severity: "hard",
      ...props,
    },
  });
}

function at(testid: string): DOMWrapper<HTMLElement> {
  const el = document.querySelector(`[data-testid="${testid}"]`);
  expect(el, `no element with data-testid="${testid}"`).toBeTruthy();
  return new DOMWrapper(el as HTMLElement);
}

const body = () => document.body.textContent ?? "";

/** The number rendered after the soft branch's "Dates below reserve:" label. */
const breachCount = () => body().match(/Dates below reserve:\s*(\d+)/)?.[1];
const shown = () => document.querySelector('[data-testid="simwarn.root"]') !== null;

describe("SimulationWarning", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  describe("when it renders at all", () => {
    it("stays hidden while closed", () => {
      mountWarning({ open: false });
      expect(shown()).toBe(false);
    });

    it("stays hidden with no simulation result, even when open", () => {
      mountWarning({ result: null });
      expect(shown()).toBe(false);
    });

    it("renders the shell but neither branch at severity 'none'", () => {
      mountWarning({ severity: "none" });
      expect(shown()).toBe(true);
      expect(body()).not.toContain("Balance Goes Negative");
      expect(body()).not.toContain("Below Reserve Threshold");
      expect(document.querySelector('[data-testid="simwarn.confirm"]')).toBeNull();
    });
  });

  describe("the hard branch", () => {
    it("headlines the negative balance and offers 'Add Anyway'", () => {
      mountWarning({ severity: "hard" });

      expect(body()).toContain("Balance Goes Negative");
      expect(body()).toContain(
        "This transaction would cause a negative balance on future dates.",
      );
      expect(at("simwarn.confirm").text()).toBe("Add Anyway");
      expect(body()).not.toContain("Below Reserve Threshold");
    });

    it("lists the negative dates and the window minimum", () => {
      mountWarning({ severity: "hard" });

      expect(body()).toContain("Negative on 2 dates:");
      expect(at("simwarn.negative-date.2026-04-20").text()).toBe("Apr 20, 2026");
      expect(body()).toContain("-12.50k");
    });

    it("truncates a long list of negative dates", () => {
      const dates = Array.from(
        { length: 13 },
        (_, i) => `2026-05-${String(i + 1).padStart(2, "0")}`,
      );
      mountWarning({ severity: "hard", result: result({ negativeDates: dates }) });

      expect(document.querySelectorAll('[data-testid^="simwarn.negative-date."]'))
        .toHaveLength(10);
      expect(body()).toContain("+ 3 more dates");
    });
  });

  describe("the soft branch", () => {
    it("headlines the reserve breach and offers 'Save Anyway'", () => {
      mountWarning({ severity: "soft" });

      expect(body()).toContain("Below Reserve Threshold");
      expect(body()).toContain(
        "Balance will drop below your configured reserve on some dates.",
      );
      expect(at("simwarn.confirm").text()).toBe("Save Anyway");
      expect(body()).not.toContain("Balance Goes Negative");
    });

    it("counts the dates below the reserve instead of listing them", () => {
      mountWarning({
        severity: "soft",
        result: result({ reserveBreachDates: ["2026-04-18", "2026-04-19"] }),
      });

      // Read the number where it is rendered: the body text is full of other
      // 2s (-12.50k, May 1, 2026), so a bare `toContain("2")` proves nothing.
      expect(body()).toContain("Dates below reserve:");
      expect(breachCount()).toBe("2");
      expect(document.querySelector('[data-testid^="simwarn.negative-date."]'))
        .toBeNull();
    });
  });

  describe.each(["hard", "soft"] as const)("the %s branch's buttons", (severity) => {
    it("emits confirm", async () => {
      const wrapper = mountWarning({ severity });
      await at("simwarn.confirm").trigger("click");
      expect(wrapper.emitted("confirm")).toHaveLength(1);
      expect(wrapper.emitted("cancel")).toBeUndefined();
    });

    it("emits cancel from the button and from the backdrop", async () => {
      const wrapper = mountWarning({ severity });
      await at("simwarn.cancel").trigger("click");
      await at("simwarn.backdrop").trigger("click");
      expect(wrapper.emitted("cancel")).toHaveLength(2);
      expect(wrapper.emitted("confirm")).toBeUndefined();
    });
  });
});
