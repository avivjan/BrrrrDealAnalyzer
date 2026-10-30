// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { mount, type VueWrapper } from "@vue/test-utils";
import { nextTick } from "vue";

import CalculationBreakdownPopup from "./CalculationBreakdownPopup.vue";
import type { CalcBreakdowns, CalcStep, CashNeededScheduleAtLowestArv } from "../../types";

let wrapper: VueWrapper | null = null;

afterEach(() => {
  wrapper?.unmount();
  wrapper = null;
  document.body.innerHTML = "";
});

const money = (label: string, value: number, extra: Partial<CalcStep> = {}): CalcStep => ({
  label,
  value,
  unit: "money",
  formula: `${label} = ${value}`,
  ...extra,
});

/** Cash Needed = Invested + Cushion; Invested = Cash to Close + Holding; Cash to Close = Down + Points. */
const BREAKDOWNS: CalcBreakdowns = {
  cash_to_close_buy: [
    money("Down Payment (cash)", 40000, { formula: "20% × Purchase ($200,000) = $40,000" }),
    money("HML Points (cash at closing)", 3220, { formula: "2% × Hard Money Loan ($161,000) = $3,220" }),
    money("Cash to Close (Buy)", 43220, {
      note: "The wire to the title company on purchase day.",
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
    money("Holding Costs (until refi)", 2400, { formula: "(Taxes + Insurance) × 180 days ÷ 360 = $2,400" }),
    money("Total Cash Invested (pre-refi)", 45620, {
      note: "Every dollar actually spent before the refinance.",
      terms: [
        { label: "Cash to Close (Buy)", value: 43220, sign: "+", step_label: "Cash to Close (Buy)" },
        { label: "Holding Costs", value: 2400, sign: "+", step_label: "Holding Costs (until refi)" },
      ],
    }),
    money("Cash Needed", 50620, {
      note: "The single out-of-pocket figure through the refinance.",
      terms: [
        { label: "Total Cash Invested", value: 45620, sign: "+", step_label: "Total Cash Invested (pre-refi)" },
        { label: "Rehab Cushion", value: 5000, sign: "+", step_label: null },
      ],
    }),
  ],
  dscr: [
    money("PITIA", 2166.67, {
      terms: [
        { label: "Mortgage", value: 1716.67, sign: "+" },
        { label: "Taxes ÷ 12", value: 450, sign: "+" },
      ],
    }),
    { label: "DSCR", value: 1.2, unit: "ratio", formula: "Rent ($2,600) ÷ PITIA ($2,166.67) = 1.20" },
  ],
  cash_out_routi_conservative: [
    money("Cash-Out Wire (Lowest ARV)", -17417.5, {
      terms: [{ label: "Refi Loan (Lowest ARV)", value: 216000, sign: "+" }, { label: "HML Payoff", value: 233417.5, sign: "-" }],
    }),
    money("Cash to Refi Table (Lowest ARV)", 17417.5, { formula: "Wire (-$17,417.50) is negative → $17,417.50 brought to the table" }),
  ],
  roi: [
    { label: "Cash on Cash", value: -2, unit: "pct", formula: "Cash Flow ≤ 0 → return undefined (-∞)" },
    { label: "ROI", value: 19.87, unit: "pct", formula: "… = 19.87%" },
  ],
};

const mountPopup = (props: Record<string, unknown> = {}) =>
  mount(CalculationBreakdownPopup, {
    attachTo: document.body,
    props: {
      open: true,
      metricLabel: "Cash Needed",
      metricKey: "total_cash_needed_for_deal",
      metricValue: 50620,
      breakdowns: BREAKDOWNS,
      ...props,
    },
  });

const popup = () => document.querySelector('[data-testid="calculation-breakdown-popup"]');
const dialog = () => document.querySelector('[role="dialog"]');
const tree = () => document.querySelector('[data-part="tree"]')!;
const rowsIn = (root: Element) => [...root.querySelectorAll('[data-part="row"]')] as HTMLElement[];
const rowByPath = (path: string) => rowsIn(document.body).find((r) => r.dataset.path === path)!;
const rowSummary = (row: HTMLElement) => [
  row.dataset.path,
  row.querySelector(':scope > div > [data-part="row-sign"]')!.textContent!.trim(),
  row.querySelector(':scope > div > [data-part="row-label"]')!.textContent!.trim(),
  row.querySelector(':scope > div > [data-part="row-value"]')!.textContent!.trim(),
];
const click = (el: Element | null) => (el as HTMLElement).click();
/** The text of a grid line: its cells joined by single spaces. */
const lineText = (line: Element) => [...line.children].map((cell) => cell.textContent!.trim()).filter(Boolean).join(" ");

describe("CalculationBreakdownPopup", () => {
  it("renders nothing while closed", async () => {
    wrapper = mountPopup({ open: false });
    await nextTick();
    expect(popup()).toBeNull();
  });

  it("teleports a dialog to body, named 'How <metric> is calculated', with the tile's value as the headline", async () => {
    wrapper = mountPopup();
    await nextTick();
    expect(popup()).not.toBeNull();
    expect(popup()!.getAttribute("data-metric-key")).toBe("total_cash_needed_for_deal");
    const heading = document.querySelector("h2")!;
    expect(heading.textContent?.trim()).toBe("How Cash Needed is calculated");
    expect(dialog()!.getAttribute("aria-labelledby")).toBe(heading.id);
    expect(document.querySelector('[data-part="headline-value"]')!.textContent?.trim()).toBe("$50,620");
  });

  it("opens on the answer: the headline's operands as rows, the total line, and the first level already open", async () => {
    wrapper = mountPopup();
    await nextTick();
    const topLevel = rowsIn(tree()).filter((r) => r.dataset.depth === "0");
    expect(topLevel.map(rowSummary)).toEqual([
      ["0", "+", "Total Cash Invested", "$45,620"],
      ["1", "+", "Rehab Cushion", "$5,000"],
    ]);
    expect(lineText(tree().querySelector('[data-part="headline-total"]')!)).toBe("= Cash Needed $50,620");
    expect(document.querySelector('[data-part="headline-note"]')!.textContent).toContain("single out-of-pocket figure");
    // Depth 1 is open: Total Cash Invested shows its operands; its own computed operands stay closed.
    expect(rowByPath("0").querySelector('[data-part="row-toggle"]')!.getAttribute("aria-expanded")).toBe("true");
    expect(rowsIn(tree()).filter((r) => r.dataset.depth === "1").map(rowSummary)).toEqual([
      ["0/0", "+", "Cash to Close (Buy)", "$43,220"],
      ["0/1", "+", "Holding Costs", "$2,400"],
    ]);
    expect(rowByPath("0/0").querySelector('[data-part="row-toggle"]')!.getAttribute("aria-expanded")).toBe("false");
    expect(rowsIn(tree()).some((r) => r.dataset.depth === "2")).toBe(false);
    expect(document.querySelector('[data-part="headline-formula"]')).toBeNull();
  });

  it("a click drills a computed row down to its rows and then to a formula, and Expand all / Collapse all cover the whole tree", async () => {
    wrapper = mountPopup();
    await nextTick();
    click(rowByPath("0/0").querySelector('[data-part="row-toggle"]'));
    await nextTick();
    expect(rowsIn(tree()).filter((r) => r.dataset.depth === "2").map(rowSummary)).toEqual([
      ["0/0/0", "+", "Down Payment", "$40,000"],
      ["0/0/1", "+", "HML Points", "$3,220"],
    ]);
    click(rowByPath("0/0/1").querySelector('[data-part="row-toggle"]'));
    await nextTick();
    expect(rowByPath("0/0/1").querySelector('[data-part="row-formula"]')!.textContent!.trim()).toBe("2% × Hard Money Loan ($161,000) = $3,220");

    click(document.querySelector('[data-part="collapse-all"]'));
    await nextTick();
    expect(rowsIn(tree()).map((r) => r.dataset.path)).toEqual(["0", "1"]);
    expect(rowByPath("0").querySelector('[data-part="row-toggle"]')!.getAttribute("aria-expanded")).toBe("false");

    click(document.querySelector('[data-part="expand-all"]'));
    await nextTick();
    expect(rowsIn(tree()).map((r) => r.dataset.path)).toEqual(["0", "0/0", "0/0/0", "0/0/1", "0/1", "1"]);
    expect(rowByPath("0/1").querySelector('[data-part="row-formula"]')!.textContent).toContain("180 days ÷ 360");
  });

  it("resets to the first level whenever it opens again on a metric", async () => {
    wrapper = mountPopup();
    await nextTick();
    click(document.querySelector('[data-part="expand-all"]'));
    await nextTick();
    expect(rowsIn(tree()).length).toBe(6);
    await wrapper.setProps({ open: false });
    await wrapper.setProps({ open: true });
    await nextTick();
    expect(rowsIn(tree()).map((r) => r.dataset.path)).toEqual(["0", "0/0", "0/1", "1"]);
  });

  it("a headline that is not a sum shows its formula first and the section's earlier steps as its inputs", async () => {
    wrapper = mountPopup({ metricLabel: "DSCR", metricKey: "dscr", metricValue: 1.2 });
    await nextTick();
    expect(document.querySelector('[data-part="headline-value"]')!.textContent?.trim()).toBe("1.20x");
    expect(document.querySelector('[data-part="headline-formula"]')!.textContent).toContain("Rent ($2,600) ÷ PITIA ($2,166.67) = 1.20");
    expect(document.querySelector('[data-part="headline-total"]')).toBeNull();
    const inputs = rowsIn(tree()).filter((r) => r.dataset.depth === "0");
    expect(inputs.map(rowSummary)).toEqual([["input/0", "", "PITIA", "$2,166.67"]]);
    // Open by default, so PITIA's operands are visible at once.
    expect(rowsIn(tree()).filter((r) => r.dataset.depth === "1").map((r) => rowSummary(r)[2])).toEqual(["Mortgage", "Taxes ÷ 12"]);
  });

  it("lists the steps the section derives after the headline under their own caption, open by default", async () => {
    wrapper = mountPopup({ metricLabel: "Cash-Out Routi (Lowest ARV)", metricKey: "cash_out_routi_conservative", metricValue: -17417.5 });
    await nextTick();
    expect(document.querySelector('[data-part="headline-value"]')!.textContent?.trim()).toBe("-$17,417.50");
    expect(document.querySelector('[data-part="derived-caption"]')!.textContent!.trim()).toBe("Derived from this");
    const derived = rowsIn(document.querySelector('[data-part="derived-tree"]')!);
    expect(derived.map(rowSummary)).toEqual([["derived/0", "", "Cash to Refi Table (Lowest ARV)", "$17,417.50"]]);
    expect(derived[0]!.querySelector('[data-part="row-formula"]')!.textContent).toContain("brought to the table");
  });

  it("formats percentage headlines by their unit, including the ±∞ sentinels", async () => {
    wrapper = mountPopup({ metricLabel: "ROI", metricKey: "roi", metricValue: 19.87 });
    await nextTick();
    expect(document.querySelector('[data-part="headline-value"]')!.textContent?.trim()).toBe("19.87%");
    expect(rowsIn(tree()).map(rowSummary)).toEqual([["input/0", "", "Cash on Cash", "-∞%"]]);
  });

  it("keeps every step in calculation order behind a collapsed 'All steps' disclosure", async () => {
    wrapper = mountPopup();
    await nextTick();
    const details = document.querySelector('[data-part="all-steps"]') as HTMLDetailsElement;
    expect(details.open).toBe(false);
    expect(details.querySelector("summary")!.textContent).toContain("All 4 steps");
    expect([...details.querySelectorAll('[data-part="all-steps-item"]')].length).toBe(4);
  });

  it("says so when the analysis carried no breakdown for this result", async () => {
    wrapper = mountPopup({ breakdowns: undefined });
    await nextTick();
    expect(document.querySelector('[data-part="empty"]')!.textContent).toContain("No breakdown available");
    expect(document.querySelector('[data-part="headline-value"]')).toBeNull();
    expect(document.querySelector('[data-part="expand-all"]')).toBeNull();
    wrapper.unmount();
    wrapper = mountPopup({ breakdowns: { total_cash_needed_for_deal: [] } });
    await nextTick();
    expect(document.querySelector('[data-part="empty"]')).not.toBeNull();
  });

  it("closes on Escape, on the scrim and from its close button — and not from a click inside the panel", async () => {
    wrapper = mountPopup();
    await nextTick();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    (popup() as HTMLElement).click();
    (document.querySelector('[data-part="close"]') as HTMLElement).click();
    (dialog() as HTMLElement).click();
    await nextTick();
    expect(wrapper.emitted("close")).toHaveLength(3);
  });

  it("claims the Escape it handles and ignores one already claimed above it", async () => {
    wrapper = mountPopup();
    await nextTick();
    const escape = new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true });
    document.dispatchEvent(escape);
    expect(escape.defaultPrevented).toBe(true);
    const claimed = new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true });
    claimed.preventDefault();
    document.dispatchEvent(claimed);
    await nextTick();
    expect(wrapper.emitted("close")).toHaveLength(1);
  });

  it("listens for Escape only while open", async () => {
    wrapper = mountPopup({ open: false });
    await nextTick();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(wrapper.emitted("close")).toBeUndefined();
    await wrapper.setProps({ open: true });
    await nextTick();
    await wrapper.setProps({ open: false });
    await nextTick();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(wrapper.emitted("close")).toBeUndefined();
  });

  it("moves focus into the panel on open, makes the rest of the page inert, and restores focus on close", async () => {
    const pressedTile = document.createElement("button");
    pressedTile.id = "pressed-tile";
    document.body.appendChild(pressedTile);
    pressedTile.focus();
    wrapper = mountPopup({ open: false });
    await wrapper.setProps({ open: true });
    await nextTick();
    await nextTick();
    expect(document.activeElement).toBe(dialog());
    expect(pressedTile.hasAttribute("inert")).toBe(true);
    await wrapper.setProps({ open: false });
    await nextTick();
    expect(pressedTile.hasAttribute("inert")).toBe(false);
    expect(document.activeElement?.id).toBe("pressed-tile");
  });
});

describe("CalculationBreakdownPopup — the Cash Needed schedule", () => {
  const SCHEDULE: CashNeededScheduleAtLowestArv = {
    dated_cash_rows: [
      { date: "2026-01-03", sequence_within_day: 0, description: "Earnest money deposit", signed_amount_dollars: "-5000.00", item_key: "earnest_money_deposit" },
      { date: "2026-01-10", sequence_within_day: 0, description: "Cash to close (the purchase wire)", signed_amount_dollars: "-38220.00", item_key: "cash_to_close_buy" },
      { date: "2026-05-01", sequence_within_day: 0, description: "HML interest for April 2026", signed_amount_dollars: "-2400.00", item_key: "hml_interest_paid_monthly" },
      { date: "2026-05-01", sequence_within_day: 1, description: "Rent collected", signed_amount_dollars: "2600.00", item_key: "pre_refi_rental_income" },
      { date: "2026-07-09", sequence_within_day: 0, description: "Cash to the refi table (Lowest-ARV refi)", signed_amount_dollars: "-2600.00", item_key: "cash_to_refi_table_conservative" },
    ],
    cash_that_must_stay_in_account: [
      { item_key: "rehab_cushion", description: "Rehab cushion: kept on hand for first draws, permits and surprises, never spent",
        amount_dollars: "5000", reserve_starts_on_date: "2026-01-10", reserve_ends_on_date: "2026-02-24" },
    ],
    dated_cash_rows_net_outflow_dollars: "45620.00",
    cash_that_must_stay_in_account_total_dollars: "5000",
    total_cash_needed_dollars: "50620.00",
  };
  const schedule = () => document.querySelector('[data-testid="cash-needed-schedule"]');

  it("shows one row per cash item, the cushion's window and the summary under the Cash Needed breakdown", async () => {
    wrapper = mountPopup({ cashNeededSchedule: SCHEDULE });
    await nextTick();
    const rows = [...schedule()!.querySelectorAll('[data-part="schedule-row"]')].map((row) =>
      [...row.querySelectorAll("td")].map((cell) => cell.textContent!.trim()).join(" "));
    expect(rows).toEqual([
      "Jan 3, 2026 Earnest money deposit -$5,000",
      "Jan 10, 2026 Cash to close (the purchase wire) -$38,220",
      "May 1, 2026 HML interest for April 2026 -$2,400",
      "May 1, 2026 Rent collected $2,600",
      "Jul 9, 2026 Cash to the refi table (Lowest-ARV refi) -$2,600",
    ]);
    expect(schedule()!.querySelector('[data-item-key="pre_refi_rental_income"] td:last-child')!.className).toContain("text-positive");
    expect(schedule()!.querySelector('[data-part="must-stay-in-account"]')!.textContent).toContain("Jan 10, 2026 → Feb 24, 2026");
    const summary = schedule()!.querySelector('[data-part="schedule-summary"]')!.textContent!.replace(/\s+/g, " ");
    expect(summary).toContain("Dated rows total (net out)$45,620");
    expect(summary).toContain("+ Rehab cushion (must stay in the account)$5,000");
    expect(summary).toContain("= Total Cash Needed$50,620");
  });

  it("is shown for Cash Needed only, and not without a schedule", async () => {
    wrapper = mountPopup({ cashNeededSchedule: SCHEDULE, metricKey: "cash_to_close_buy", metricLabel: "Cash to Close", metricValue: 43220 });
    await nextTick();
    expect(schedule()).toBeNull();
    wrapper.unmount();
    wrapper = mountPopup({ cashNeededSchedule: null });
    await nextTick();
    expect(schedule()).toBeNull();
  });
});
