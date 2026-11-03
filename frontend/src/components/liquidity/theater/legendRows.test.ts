import { describe, expect, it } from "vitest";

import type { LiquidityTransaction } from "../../../types/liquidity";
import { groupOpenRowsOfDealByMonth } from "./legendRows";

const row = (id: string, effective_date: string, amount_dollars: number, over: Partial<LiquidityTransaction> = {}): LiquidityTransaction => ({
  id, effective_date, description: `Row ${id}`, amount_dollars, source_deal_board: "my_deals", source_deal_id: "d1", ...over,
});

describe("groupOpenRowsOfDealByMonth", () => {
  const rows = [
    row("dec-2", "2026-12-15", -1000),
    row("nov-1", "2026-11-20", -385, { sequence_within_day: 2 }),
    row("nov-0", "2026-11-20", 5665, { sequence_within_day: 1 }),
    row("dec-1", "2026-12-01", -1500, { created_because_refi_is_late: true }),
    row("done", "2026-11-05", -200, { done_at: "2026-11-05T00:00:00Z" }),
    row("other-deal", "2026-11-21", -50, { source_deal_id: "d2" }),
    row("manual", "2026-11-22", -80, { source_deal_board: null, source_deal_id: null }),
  ];

  it("groups the deal's open rows by month, in date and day order, with each month's net", () => {
    const months = groupOpenRowsOfDealByMonth(rows, "my_deals:d1");
    expect(months.map((month) => [month.monthKey, month.monthLabel, month.rows.map((item) => item.id), month.netDollars])).toEqual([
      ["2026-11", "Nov 2026", ["nov-0", "nov-1"], 5280],
      ["2026-12", "Dec 2026", ["dec-1", "dec-2"], -2500],
    ]);
  });

  it("leaves out done rows, other deals' rows and manual rows; keeps the late-refi flag on its row", () => {
    const ids = groupOpenRowsOfDealByMonth(rows, "my_deals:d1").flatMap((month) => month.rows.map((item) => item.id));
    expect(ids).not.toContain("done");
    expect(ids).not.toContain("other-deal");
    expect(ids).not.toContain("manual");
    const december = groupOpenRowsOfDealByMonth(rows, "my_deals:d1")[1]!;
    expect(december.rows[0]!.created_because_refi_is_late).toBe(true);
  });

  it("is empty for a deal with no open row", () => {
    expect(groupOpenRowsOfDealByMonth(rows, "bought:none")).toEqual([]);
  });
});
