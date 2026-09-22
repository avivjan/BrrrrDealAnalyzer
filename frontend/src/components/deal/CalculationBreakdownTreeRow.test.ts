// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import CalculationBreakdownTreeRow from "./CalculationBreakdownTreeRow.vue";
import type { CalculationBreakdownRow } from "./calculationBreakdownTree";
import type { CalcBreakdowns, CalcStep } from "../../types";

const HML_POINTS: CalcStep = {
  label: "HML Points (cash at closing)",
  value: 3220,
  unit: "money",
  formula: "2% × Hard Money Loan ($161,000) = $3,220",
};
const CASH_TO_CLOSE: CalcStep = {
  label: "Cash to Close (Buy)",
  value: 43220,
  unit: "money",
  formula: "Down Payment ($40,000) + HML Points ($3,220) = $43,220",
  note: "The wire to the title company on purchase day.",
  terms: [
    { label: "Down Payment", value: 40000, sign: "+" },
    { label: "HML Points", value: 3220, sign: "+", step_label: "HML Points (cash at closing)" },
  ],
};
const BREAKDOWNS: CalcBreakdowns = { cash_to_close_buy: [HML_POINTS, CASH_TO_CLOSE] };

const linkedRow: CalculationBreakdownRow = { path: "0", sign: "+", label: "Cash to Close (Buy)", value: 43220, unit: "money", linkedStep: CASH_TO_CLOSE };
const leafRow: CalculationBreakdownRow = { path: "1", sign: "-", label: "Earnest Money Deposit", value: 5000, unit: "money" };
const ratioRow: CalculationBreakdownRow = { path: "input/0", sign: null, label: "DSCR", value: 1.2, unit: "ratio", linkedStep: { label: "DSCR", value: 1.2, unit: "ratio", formula: "Rent ÷ PITIA = 1.20" } };

const mountRow = (row: CalculationBreakdownRow, expanded: string[] = []) =>
  mount(CalculationBreakdownTreeRow, {
    props: {
      row,
      depth: 0,
      ancestorStepLabels: new Set<string>(),
      expandedRowPaths: new Set(expanded),
      breakdowns: BREAKDOWNS,
      sectionKey: "cash_to_close_buy",
    },
  });

describe("CalculationBreakdownTreeRow", () => {
  it("renders sign, label and value, with a chevron only on a row that is a computed step", () => {
    const linked = mountRow(linkedRow);
    expect(linked.get('[data-part="row-sign"]').text()).toBe("+");
    expect(linked.get('[data-part="row-label"]').text()).toBe("Cash to Close (Buy)");
    expect(linked.get('[data-part="row-value"]').text()).toBe("$43,220");
    expect(linked.get('[data-part="row-toggle"]').attributes("aria-expanded")).toBe("false");
    expect(linked.attributes("data-expandable")).toBe("true");

    const leaf = mountRow(leafRow);
    expect(leaf.get('[data-part="row-sign"]').text()).toBe("-");
    expect(leaf.find('[data-part="row-toggle"]').exists()).toBe(false);
    expect(leaf.find('[data-part="row-children"]').exists()).toBe(false);
    expect(leaf.attributes("data-expandable")).toBe("false");
  });

  it("emits toggle from the chevron and from the row itself, never from a leaf", async () => {
    const linked = mountRow(linkedRow);
    await linked.get('[data-part="row-toggle"]').trigger("click");
    await linked.get('[data-part="row-label"]').trigger("click");
    expect(linked.emitted("toggle")).toEqual([["0"], ["0"]]);
    const leaf = mountRow(leafRow);
    await leaf.get('[data-part="row-label"]').trigger("click");
    expect(leaf.emitted("toggle")).toBeUndefined();
  });

  it("when open, a sum step shows its operands as nested rows with a total line and its note", () => {
    const wrapper = mountRow(linkedRow, ["0"]);
    expect(wrapper.get('[data-part="row-toggle"]').attributes("aria-expanded")).toBe("true");
    const children = wrapper.get('[data-part="row-children"]');
    expect(wrapper.get('[data-part="row-toggle"]').attributes("aria-controls")).toBe(children.attributes("id"));
    const nested = children.findAll('[data-part="row"]');
    expect(nested.map((r) => r.attributes("data-path"))).toEqual(["0/0", "0/1"]);
    expect(nested.map((r) => r.get('[data-part="row-label"]').text())).toEqual(["Down Payment", "HML Points"]);
    expect(nested[1]!.attributes("data-expandable")).toBe("true");
    expect(nested[0]!.attributes("data-expandable")).toBe("false");
    const totalLine = children.get('[data-part="row-total"]').element;
    expect([...totalLine.children].map((cell) => cell.textContent!.trim()).filter(Boolean).join(" ")).toBe("= Cash to Close (Buy) $43,220");
    expect(children.get('[data-part="row-note"]').text()).toBe("The wire to the title company on purchase day.");
  });

  it("when open, a step that is not a sum shows its formula instead of rows", () => {
    const wrapper = mountRow(ratioRow, ["input/0"]);
    expect(wrapper.get('[data-part="row-sign"]').text()).toBe("");
    expect(wrapper.get('[data-part="row-value"]').text()).toBe("1.20x");
    expect(wrapper.find('[data-part="row-total"]').exists()).toBe(false);
    expect(wrapper.get('[data-part="row-formula"]').text()).toBe("Rent ÷ PITIA = 1.20");
  });

  it("drills a nested computed row down to its own formula when its path is open too", () => {
    const wrapper = mountRow(linkedRow, ["0", "0/1"]);
    const hmlPoints = wrapper.findAll('[data-part="row"]').find((r) => r.attributes("data-path") === "0/1")!;
    expect(hmlPoints.get('[data-part="row-formula"]').text()).toBe("2% × Hard Money Loan ($161,000) = $3,220");
  });
});
