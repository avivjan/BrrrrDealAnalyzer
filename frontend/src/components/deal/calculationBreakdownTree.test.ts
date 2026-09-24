import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import type { CalcBreakdowns, CalcStep } from "../../types";
import {
  allExpandableRowPaths,
  defaultExpandedRowPaths,
  findHeadlineStepIndex,
  findStepByLabel,
  rowsOfStep,
  rowsOfSteps,
  stepsAfterHeadline,
  topLevelRowsForHeadline,
} from "./calculationBreakdownTree";
import { formatCalculationStepValueByUnit } from "./calculationStepFormat";
import { BRRRR_REPORT_RESULT_TILES, FLIP_REPORT_RESULT_TILES } from "./reportResultTiles";

const money = (label: string, value: number, extra: Partial<CalcStep> = {}): CalcStep => ({
  label,
  value,
  unit: "money",
  formula: `${label} = ${value}`,
  ...extra,
});

/** A small deal: Cash Needed = Invested + Cushion; Invested = Cash to Close + Holding; Cash to Close = Down + Points. */
const FIXTURE: CalcBreakdowns = {
  cash_to_close_buy: [
    money("Down Payment (cash)", 40000),
    money("HML Points (cash at closing)", 3220, { formula: "2% × Hard Money Loan ($161,000) = $3,220" }),
    money("Cash to Close (Buy)", 43220, {
      terms: [
        { label: "Down Payment", value: 40000, sign: "+", step_label: "Down Payment (cash)" },
        { label: "HML Points", value: 3220, sign: "+", step_label: "HML Points (cash at closing)" },
      ],
    }),
  ],
  total_cash_needed_for_deal: [
    money("Cash to Close (Buy)", 43220, {
      terms: [
        { label: "Down Payment", value: 40000, sign: "+", step_label: "Down Payment (cash)" },
        { label: "HML Points", value: 3220, sign: "+", step_label: "HML Points (cash at closing)" },
      ],
    }),
    money("Holding Costs (until refi)", 2400, { note: "Taxes, insurance and HOA until the refi." }),
    money("Total Cash Invested (pre-refi)", 45620, {
      terms: [
        { label: "Cash to Close (Buy)", value: 43220, sign: "+", step_label: "Cash to Close (Buy)" },
        { label: "Holding Costs", value: 2400, sign: "+", step_label: "Holding Costs (until refi)" },
      ],
    }),
    money("Cash Needed", 50620, {
      terms: [
        { label: "Total Cash Invested", value: 45620, sign: "+", step_label: "Total Cash Invested (pre-refi)" },
        { label: "Rehab Cushion", value: 5000, sign: "+", step_label: null },
      ],
    }),
  ],
  dscr: [
    money("PITIA", 2166.67, { terms: [{ label: "Mortgage", value: 1716.67, sign: "+", step_label: "Monthly Mortgage Payment" }, { label: "Taxes ÷ 12", value: 450, sign: "+" }] }),
    { label: "DSCR", value: 1.2, unit: "ratio", formula: "Rent ($2,600) ÷ PITIA ($2,166.67) = 1.20" },
  ],
};

describe("calculationBreakdownTree", () => {
  it("finds the headline by the tile's value, falling back to the last step", () => {
    const steps = FIXTURE.total_cash_needed_for_deal!;
    expect(findHeadlineStepIndex(steps, 45620)).toBe(2);
    expect(findHeadlineStepIndex(steps, 50620)).toBe(3);
    expect(findHeadlineStepIndex(steps, 1)).toBe(3);
    expect(findHeadlineStepIndex(steps, undefined)).toBe(3);
    expect(findHeadlineStepIndex([], 1)).toBe(-1);
  });

  it("looks a step up in the referring section first, then in any section", () => {
    expect(findStepByLabel(FIXTURE, "total_cash_needed_for_deal", "Cash to Close (Buy)")).toBe(FIXTURE.total_cash_needed_for_deal![0]);
    expect(findStepByLabel(FIXTURE, "total_cash_needed_for_deal", "HML Points (cash at closing)")).toBe(FIXTURE.cash_to_close_buy![1]);
    expect(findStepByLabel(FIXTURE, "total_cash_needed_for_deal", "Nowhere")).toBeUndefined();
  });

  it("turns a sum headline into its operand rows, linked where the backend named a step", () => {
    const rows = topLevelRowsForHeadline(FIXTURE, "total_cash_needed_for_deal", 3);
    expect(rows.map((r) => [r.path, r.sign, r.label, r.value, r.linkedStep?.label])).toEqual([
      ["0", "+", "Total Cash Invested", 45620, "Total Cash Invested (pre-refi)"],
      ["1", "+", "Rehab Cushion", 5000, undefined],
    ]);
    expect(defaultExpandedRowPaths(rows)).toEqual(["0"]);
  });

  it("drills a linked row down to its own operands and stops at raw inputs", () => {
    const [invested] = topLevelRowsForHeadline(FIXTURE, "total_cash_needed_for_deal", 3);
    const investedRows = rowsOfStep(invested!.linkedStep!, FIXTURE, "total_cash_needed_for_deal", invested!.path, new Set(["Cash Needed", invested!.linkedStep!.label]));
    expect(investedRows.map((r) => [r.path, r.label, r.linkedStep?.label])).toEqual([
      ["0/0", "Cash to Close (Buy)", "Cash to Close (Buy)"],
      ["0/1", "Holding Costs", "Holding Costs (until refi)"],
    ]);
    const cashToCloseRows = rowsOfStep(investedRows[0]!.linkedStep!, FIXTURE, "total_cash_needed_for_deal", "0/0", new Set());
    expect(cashToCloseRows.map((r) => [r.path, r.label, r.linkedStep?.label])).toEqual([
      ["0/0/0", "Down Payment", "Down Payment (cash)"],
      ["0/0/1", "HML Points", "HML Points (cash at closing)"],
    ]);
    // A non-sum step has no rows of its own: its formula is what gets shown.
    expect(rowsOfStep(cashToCloseRows[1]!.linkedStep!, FIXTURE, "total_cash_needed_for_deal", "0/0/1", new Set())).toEqual([]);
  });

  it("enumerates every expandable path for Expand all, and a cycle never recurses", () => {
    const rows = topLevelRowsForHeadline(FIXTURE, "total_cash_needed_for_deal", 3);
    expect(allExpandableRowPaths(rows, FIXTURE, "total_cash_needed_for_deal", new Set(["Cash Needed"]))).toEqual([
      "0", "0/0", "0/0/0", "0/0/1", "0/1",
    ]);
    const cyclic: CalcBreakdowns = {
      loop: [money("A", 1, { terms: [{ label: "B", value: 1, sign: "+", step_label: "B" }] }), money("B", 1, { terms: [{ label: "A", value: 1, sign: "+", step_label: "A" }] })],
    };
    const loopRows = topLevelRowsForHeadline(cyclic, "loop", 1);
    expect(allExpandableRowPaths(loopRows, cyclic, "loop", new Set(["B"]))).toEqual(["0"]);
  });

  it("lists a non-sum headline's earlier steps as its input rows, and the steps after a headline separately", () => {
    const rows = topLevelRowsForHeadline(FIXTURE, "dscr", 1);
    expect(rows.map((r) => [r.path, r.sign, r.label, r.unit, r.linkedStep?.label])).toEqual([["input/0", null, "PITIA", "money", "PITIA"]]);
    expect(stepsAfterHeadline(FIXTURE.total_cash_needed_for_deal!, 2).map((s) => s.label)).toEqual(["Cash Needed"]);
    expect(stepsAfterHeadline(FIXTURE.dscr!, -1)).toEqual([]);
  });
});

describe("calculationBreakdownTree against the backend's recorded breakdown", () => {
  // The golden the backend's own regression harness records for its fixture deal, read in place so a
  // stale copy can never drift from the contract (the CI job checks out the whole repository).
  const here = dirname(fileURLToPath(import.meta.url));
  const goldenPath = join(here, "../../../../BackEnd/tests/_regression_snapshots/calculations.json");
  const recorded = JSON.parse(readFileSync(goldenPath, "utf8")) as { brrr: { baseline: { body: { breakdowns: CalcBreakdowns; total_cash_needed_for_deal: number } } } };
  const breakdowns = recorded.brrr.baseline.body.breakdowns;
  const section = "total_cash_needed_for_deal";

  it("resolves Cash Needed → Cash Needed through Refi → Total Cash Invested → Cash to Close → HML Points, with raw inputs as leaves", () => {
    const steps = breakdowns[section]!;
    const headlineIndex = findHeadlineStepIndex(steps, recorded.brrr.baseline.body.total_cash_needed_for_deal);
    expect(steps[headlineIndex]!.label).toBe("Cash Needed");
    const rows = topLevelRowsForHeadline(breakdowns, section, headlineIndex);
    const byLabel = (list: ReturnType<typeof topLevelRowsForHeadline>, label: string) => list.find((r) => r.label === label)!;
    expect(rows.map((r) => r.label)).toEqual(["Cash Needed through Refi", "Floor Top-Up"]);
    // The top-up is a max(), not a sum: it expands into its formula, which names the floor.
    const floorTopUp = byLabel(rows, "Floor Top-Up");
    expect(floorTopUp.linkedStep?.terms).toBeFalsy();
    expect(floorTopUp.linkedStep?.formula).toContain("the floor ($55,244.57)");
    const throughRefi = byLabel(rows, "Cash Needed through Refi");
    expect(throughRefi.linkedStep?.label).toBe("Cash Needed through Refi");
    const throughRefiRows = rowsOfStep(throughRefi.linkedStep!, breakdowns, section, throughRefi.path, new Set());
    const invested = byLabel(throughRefiRows, "Total Cash Invested");
    expect(invested.linkedStep?.label).toBe("Total Cash Invested (pre-refi)");
    expect(byLabel(throughRefiRows, "Rehab Cushion").linkedStep).toBeUndefined();
    const investedRows = rowsOfStep(invested.linkedStep!, breakdowns, section, invested.path, new Set());
    expect(byLabel(investedRows, "Earnest Money Deposit").linkedStep).toBeUndefined();
    const cashToClose = byLabel(investedRows, "Cash to Close (Buy)");
    expect(cashToClose.linkedStep?.label).toBe("Cash to Close (Buy)");
    const cashToCloseRows = rowsOfStep(cashToClose.linkedStep!, breakdowns, section, cashToClose.path, new Set());
    const hmlPoints = byLabel(cashToCloseRows, "HML Points");
    expect(hmlPoints.linkedStep?.label).toBe("HML Points (cash at closing)");
    expect(hmlPoints.linkedStep?.formula).toContain("Hard Money Loan");
    const noiRows = rowsOfStep(breakdowns.cash_flow!.find((s) => s.label === "Net Operating Income (NOI)")!, breakdowns, "cash_flow", "x", new Set());
    expect(byLabel(noiRows, "Rent").linkedStep).toBeUndefined();
  });
});

describe("calculationBreakdownTree matches the PDF's Python port", () => {
  // `__fixtures__/calculationBreakdownTreeParity.json` is the popup's fully expanded tree for every
  // result tile of the recorded baseline deals, as `BackEnd/BL/reports/common/breakdown_tree.py`
  // builds it (`BackEnd/tests/test_report_pdf.py` records and checks it). Building the same tree
  // here from the same goldens proves the PDF shows the popup's rows and numbers.
  const here = dirname(fileURLToPath(import.meta.url));
  const recorded = JSON.parse(
    readFileSync(join(here, "../../../../BackEnd/tests/_regression_snapshots/calculations.json"), "utf8"),
  ) as { brrr: { baseline: { body: Record<string, unknown> } }; flip: { baseline: { body: Record<string, unknown> } } };
  const parity = JSON.parse(readFileSync(join(here, "__fixtures__/calculationBreakdownTreeParity.json"), "utf8")) as Record<
    string,
    Record<string, unknown>
  >;

  type ParityRow = {
    path: string;
    sign: "+" | "-" | null;
    label: string;
    value: number;
    unit: string;
    linkedStepLabel: string | null;
    formattedValue: string;
  };

  function expandedRows(
    rows: ReturnType<typeof topLevelRowsForHeadline>,
    breakdowns: CalcBreakdowns,
    sectionKey: string,
    ancestorStepLabels: ReadonlySet<string>,
  ): ParityRow[] {
    return rows.flatMap((row) => {
      const flattened: ParityRow[] = [{
        path: row.path,
        sign: row.sign,
        label: row.label,
        value: row.value,
        unit: row.unit ?? "money",
        linkedStepLabel: row.linkedStep?.label ?? null,
        formattedValue: formatCalculationStepValueByUnit(row.unit, row.value),
      }];
      if (!row.linkedStep) return flattened;
      const ancestors = new Set(ancestorStepLabels);
      ancestors.add(row.linkedStep.label);
      const children = rowsOfStep(row.linkedStep, breakdowns, sectionKey, row.path, ancestors);
      return [...flattened, ...expandedRows(children, breakdowns, sectionKey, ancestors)];
    });
  }

  for (const [dealType, body, tiles] of [
    ["BRRRR", recorded.brrr.baseline.body, BRRRR_REPORT_RESULT_TILES],
    ["FLIP", recorded.flip.baseline.body, FLIP_REPORT_RESULT_TILES],
  ] as const) {
    it(`builds the same ${dealType} trees, row for row and number for number`, () => {
      const breakdowns = body.breakdowns as CalcBreakdowns;
      const built: Record<string, unknown> = {};
      for (const tile of tiles) {
        const steps = breakdowns[tile.resultKey]!;
        const headlineIndex = findHeadlineStepIndex(steps, body[tile.resultKey] as number);
        const headlineLabel = steps[headlineIndex]!.label;
        built[tile.resultKey] = {
          headlineStepIndex: headlineIndex,
          headlineStepLabel: headlineLabel,
          rows: expandedRows(topLevelRowsForHeadline(breakdowns, tile.resultKey, headlineIndex), breakdowns, tile.resultKey, new Set([headlineLabel])),
          derivedRows: expandedRows(rowsOfSteps(stepsAfterHeadline(steps, headlineIndex), "derived"), breakdowns, tile.resultKey, new Set()),
        };
      }
      expect(built).toEqual(parity[dealType]);
    });
  }
});
