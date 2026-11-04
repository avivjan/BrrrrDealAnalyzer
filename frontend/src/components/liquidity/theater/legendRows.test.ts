import { describe, expect, it } from "vitest";

import type { DealKeyDate, DealMilestoneState, LiquidityTransaction } from "../../../types/liquidity";
import { dealTimelineByMonth, doneTransactionsOnDate, monthToOpenFirst, recentOccurrencesOfRule } from "./legendRows";

const row = (id: string, effective_date: string, amount_dollars: number, over: Partial<LiquidityTransaction> = {}): LiquidityTransaction => ({
  id, effective_date, description: `Row ${id}`, amount_dollars, source_deal_board: "my_deals", source_deal_id: "d1", ...over,
});

const ROWS = [
  row("dec-2", "2026-12-15", -1000),
  row("nov-1", "2026-11-20", -385, { sequence_within_day: 2 }),
  row("nov-0", "2026-11-20", 5665, { sequence_within_day: 1 }),
  row("dec-1", "2026-12-01", -1500, { created_because_refi_is_late: true }),
  row("done", "2026-11-05", -200, { done_at: "2026-11-05T00:00:00Z" }),
  row("other-deal", "2026-11-21", -50, { source_deal_id: "d2" }),
  row("manual", "2026-11-22", -80, { source_deal_board: null, source_deal_id: null }),
];
const KEY_DATES: DealKeyDate[] = [
  { key: "rehab_completed", date: "2026-11-20", description: "Rehab completed" },
  { key: "property_tax_bill_paid_on_november_30", date: "2026-11-30", description: "Property tax bill paid from the tax bucket (Nov 30)" },
];
const MILESTONES: DealMilestoneState[] = [{ milestone: "rehab_completed", planned_date: "2026-11-20", approved_at: null, is_overdue: false }];

describe("dealTimelineByMonth", () => {
  it("merges the key dates and every row of the deal, open and done, by month, a key date first on its day", () => {
    const months = dealTimelineByMonth(ROWS, "my_deals:d1", KEY_DATES, MILESTONES);
    const describe = (item: (typeof months)[number]["items"][number]) => (item.kind === "key_date" ? `key:${item.keyDate.key}` : item.transaction.id);
    expect(months.map((month) => [month.monthKey, month.monthLabel, month.items.map(describe)])).toEqual([
      ["2026-11", "Nov 2026", ["done", "key:rehab_completed", "nov-0", "nov-1", "key:property_tax_bill_paid_on_november_30"]],
      ["2026-12", "Dec 2026", ["dec-1", "dec-2"]],
    ]);
  });

  it("counts each month's rows and done rows, and nets every row in it", () => {
    const [november, december] = dealTimelineByMonth(ROWS, "my_deals:d1", KEY_DATES, MILESTONES);
    expect([november!.transactionCount, november!.doneTransactionCount, november!.netDollars]).toEqual([3, 1, 5080]);
    expect([december!.transactionCount, december!.doneTransactionCount, december!.netDollars]).toEqual([2, 0, -2500]);
  });

  it("gives a key date its milestone's state, and none to the Nov 30 bill", () => {
    const [november] = dealTimelineByMonth(ROWS, "my_deals:d1", KEY_DATES, MILESTONES);
    const keyDates = november!.items.filter((item) => item.kind === "key_date");
    expect(keyDates.map((item) => (item.kind === "key_date" ? item.milestoneState?.milestone ?? null : null))).toEqual(["rehab_completed", null]);
  });

  it("leaves out other deals' rows and manual rows", () => {
    const ids = dealTimelineByMonth(ROWS, "my_deals:d1", [], []).flatMap((month) =>
      month.items.flatMap((item) => (item.kind === "transaction" ? [item.transaction.id] : [])));
    expect(ids).not.toContain("other-deal");
    expect(ids).not.toContain("manual");
  });
});

describe("monthToOpenFirst", () => {
  const months = dealTimelineByMonth(ROWS, "my_deals:d1", KEY_DATES, MILESTONES);

  it("opens this month when the deal has something in it", () => {
    expect(monthToOpenFirst(months, "2026-12-03")).toBe("2026-12");
  });

  it("otherwise opens the first month with an open row", () => {
    expect(monthToOpenFirst(months, "2027-03-01")).toBe("2026-11");
    const onlyDoneInNovember = dealTimelineByMonth([row("done", "2026-11-05", -1, { done_at: "x" }), row("open", "2027-01-05", -1)], "my_deals:d1", [], []);
    expect(monthToOpenFirst(onlyDoneInNovember, "2027-03-01")).toBe("2027-01");
  });
});

describe("doneTransactionsOnDate", () => {
  it("lists the one-off rows of a day that are marked done, deal and manual alike", () => {
    const rows = [
      row("done-deal", "2026-11-05", -200, { done_at: "2026-11-05T00:00:00Z" }),
      row("done-manual", "2026-11-05", -80, { done_at: "2026-11-06T00:00:00Z", source_deal_board: null, source_deal_id: null }),
      row("open", "2026-11-05", -10),
      row("other-day", "2026-11-06", -10, { done_at: "2026-11-06T00:00:00Z" }),
    ];
    expect(doneTransactionsOnDate(rows, "2026-11-05").map((item) => item.id)).toEqual(["done-deal", "done-manual"]);
  });
});

describe("recurring occurrences in the legend and the day view", () => {
  const occurrence = (index: number, scheduled: string, over: Partial<LiquidityTransaction> = {}): LiquidityTransaction => ({
    id: `recurring:r1:${index}`, effective_date: scheduled, description: "Misc", amount_dollars: -1500,
    recurring_rule_id: "r1", recurring_index: index, recurring_scheduled_date: scheduled, ...over,
  });

  it("lists a rule's occurrences up to today, then the next two, leaving history out", () => {
    const occurrences = [
      occurrence(0, "2026-08-01", { recurring_is_history: true }),
      occurrence(3, "2026-11-01"), occurrence(1, "2026-09-01", { done_at: "x" }), occurrence(2, "2026-10-01"),
      occurrence(4, "2026-12-01"), occurrence(5, "2027-01-01"), occurrence(6, "2027-02-01"),
      { ...occurrence(1, "2026-09-01"), id: "recurring:other:1", recurring_rule_id: "other" },
    ];
    expect(recentOccurrencesOfRule(occurrences, "r1", "2026-11-04").map((item) => item.recurring_scheduled_date)).toEqual([
      "2026-09-01", "2026-10-01", "2026-11-01", "2026-12-01", "2027-01-01",
    ]);
  });

  it("puts a done occurrence in its day's done list, but not a historical one", () => {
    const done = occurrence(1, "2026-11-05", { done_at: "2026-11-05T00:00:00Z" });
    const history = occurrence(0, "2026-11-05", { done_at: "2026-11-05T00:00:00Z", recurring_is_history: true, id: "h" });
    expect(doneTransactionsOnDate([done, history], "2026-11-05").map((item) => item.id)).toEqual(["recurring:r1:1"]);
  });
});
