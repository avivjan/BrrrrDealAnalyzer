// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import CashNeededScheduleTable from "./CashNeededScheduleTable.vue";
import type { CashNeededScheduleAtLowestArv } from "../../types";

const cashRow = (date: string, sequence_within_day: number, description: string, signed_amount_dollars: string, item_key: string) =>
  ({ date, sequence_within_day, description, signed_amount_dollars, item_key });

const SCHEDULE: CashNeededScheduleAtLowestArv = {
  dated_cash_rows: [
    cashRow("2026-01-03", 0, "Earnest money deposit", "-5000.00", "earnest_money_deposit"),
    cashRow("2026-01-10", 0, "Cash to close (the purchase wire)", "-45364.01", "cash_to_close_buy"),
    cashRow("2026-01-11", 0, "Seller tax credit set aside in the tax bucket", "-88.77", "seller_tax_credit_set_aside_in_tax_bucket"),
    cashRow("2026-07-09", 0, "Tax bucket balance released (Lowest-ARV refi)", "120.00", "property_tax_bucket_balance_released_at_refi"),
  ],
  deal_milestones: [
    { date: "2026-01-03", milestone_key: "contract_signed", description: "Contract signed" },
    { date: "2026-01-10", milestone_key: "purchase_closed", description: "Purchase closing" },
    { date: "2026-07-09", milestone_key: "refi_closed", description: "Refi closing" },
  ],
};

const mountTable = (schedule: CashNeededScheduleAtLowestArv) => mount(CashNeededScheduleTable, { props: { schedule } });
const lineTexts = (wrapper: ReturnType<typeof mountTable>) =>
  wrapper.findAll("tbody tr").map((row) => `${row.attributes("data-part")}: ${row.findAll("td").map((cell) => cell.text().trim()).join(" ")}`);

describe("CashNeededScheduleTable — the deal's key dates among the cash rows", () => {
  it("lists every key date in date order, first on its day", () => {
    expect(lineTexts(mountTable(SCHEDULE))).toEqual([
      "schedule-milestone: Jan 3, 2026 Contract signed",
      "schedule-row: Jan 3, 2026 Earnest money deposit -$5,000",
      "schedule-milestone: Jan 10, 2026 Purchase closing",
      "schedule-row: Jan 10, 2026 Cash to close (the purchase wire) -$45,364.01",
      "schedule-row: Jan 11, 2026 Seller tax credit set aside in the tax bucket -$88.77",
      "schedule-milestone: Jul 9, 2026 Refi closing",
      "schedule-row: Jul 9, 2026 Tax bucket balance released (Lowest-ARV refi) $120",
    ]);
  });

  it("styles a key date apart from the transactions: tinted, uppercase, a flag, no amount", () => {
    const wrapper = mountTable(SCHEDULE);
    const milestone = wrapper.get('[data-part="schedule-milestone"][data-milestone-key="purchase_closed"]');
    expect(milestone.classes()).toEqual(expect.arrayContaining(["bg-primary/10", "text-primary"]));
    const cells = milestone.findAll("td");
    expect(cells).toHaveLength(2);
    expect(cells[1]!.attributes("colspan")).toBe("2");
    expect(cells[1]!.classes()).toEqual(expect.arrayContaining(["uppercase", "font-semibold", "text-[11px]"]));
    expect(cells[1]!.find("i.pi-flag").attributes("aria-hidden")).toBe("true");

    const transaction = wrapper.get('[data-part="schedule-row"][data-item-key="cash_to_close_buy"]');
    expect(transaction.findAll("td")).toHaveLength(3);
    expect(transaction.findAll("td")[1]!.classes()).not.toContain("uppercase");
  });

  it("keeps the cash rows exactly as before (money in in the positive colour)", () => {
    const wrapper = mountTable(SCHEDULE);
    expect(wrapper.findAll('[data-part="schedule-row"]')).toHaveLength(4);
    expect(wrapper.get('[data-item-key="property_tax_bucket_balance_released_at_refi"] td:last-child').classes()).toContain("text-positive");
  });

  it("shows only the cash rows for a result saved before the key dates existed", () => {
    const wrapper = mountTable({ dated_cash_rows: SCHEDULE.dated_cash_rows });
    expect(wrapper.findAll('[data-part="schedule-milestone"]')).toHaveLength(0);
    expect(wrapper.findAll('[data-part="schedule-row"]')).toHaveLength(4);
  });
});
