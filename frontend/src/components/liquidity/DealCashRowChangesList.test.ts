// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import DealCashRowChangesList from "./DealCashRowChangesList.vue";
import type { DealCashRowChange } from "../../types/liquidity";

function change(overrides: Partial<DealCashRowChange>): DealCashRowChange {
  return {
    change_kind: "unchanged", item_key: "hoa_dues", occurrence_number: 1, description: "HOA dues",
    transaction_id: "txn-hoa", date_before: "2026-12-01", date_after: "2026-12-01", amount_dollars_before: -100, amount_dollars_after: -100,
    deal_date_not_applied_because_you_changed_it: null, deal_amount_dollars_not_applied_because_you_changed_it: null,
    created_because_refi_is_late: false, ...overrides,
  };
}

const CHANGES = [
  change({}),
  change({ change_kind: "updated", item_key: "cash_to_close_buy", transaction_id: "txn-close", description: "Cash to close",
    date_before: "2026-01-10", date_after: "2026-01-12", amount_dollars_before: -50000, amount_dollars_after: -50100 }),
  change({ change_kind: "updated", item_key: "construction_account_deposit", transaction_id: "txn-cushion", description: "Deposit into the construction account (rehab cushion)",
    date_before: "2026-01-10", date_after: "2026-01-12", amount_dollars_before: -1800, amount_dollars_after: -1800,
    deal_amount_dollars_not_applied_because_you_changed_it: -2100 }),
  change({ change_kind: "added", item_key: "hml_interest_paid_monthly", occurrence_number: 7, transaction_id: null, description: "HML interest",
    date_before: null, date_after: "2026-08-01", amount_dollars_before: null, amount_dollars_after: -1800, created_because_refi_is_late: true }),
];

describe("DealCashRowChangesList", () => {
  it("lists the changed rows with before -> after and folds the unchanged ones", async () => {
    const wrapper = mount(DealCashRowChangesList, { props: { changes: CHANGES, useDealValueFor: [] } });
    const rows = wrapper.findAll('[data-testid="deal-cash-row-change"]');
    expect(rows.map((row) => row.attributes("data-change-kind"))).toEqual(["updated", "updated", "added"]);
    expect(rows[0]!.text()).toContain("Jan 10, 2026 → Jan 12, 2026");
    expect(rows[0]!.text()).toContain("-$50,000 → -$50,100");
    expect(rows[2]!.text()).toContain("Refi late");
    await wrapper.get('[data-testid="deal-cash-row-changes.toggle-unchanged"]').trigger("click");
    expect(wrapper.text()).toContain("HOA dues");
  });

  it("names the kept override and toggles the deal's value", async () => {
    const wrapper = mount(DealCashRowChangesList, { props: { changes: CHANGES, useDealValueFor: [] } });
    const conflict = wrapper.get('[data-testid="deal-cash-row-amount-conflict"]');
    expect(conflict.text()).toContain("Kept your -$1,800 (the deal now says -$2,100)");
    await conflict.get("button").trigger("click");
    expect(wrapper.emitted("update:useDealValueFor")).toEqual([[[{ transaction_id: "txn-cushion", field: "amount" }]]]);

    await wrapper.setProps({ useDealValueFor: [{ transaction_id: "txn-cushion", field: "amount" }] });
    expect(wrapper.get('[data-testid="deal-cash-row-amount-conflict"] button').text()).toBe("Keep my amount");
    await wrapper.get('[data-testid="deal-cash-row-amount-conflict"] button').trigger("click");
    expect(wrapper.emitted("update:useDealValueFor")?.[1]).toEqual([[]]);
  });
});
