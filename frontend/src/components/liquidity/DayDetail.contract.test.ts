// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import DayDetail from "./DayDetail.vue";
import type { DayBucket, LiquidityTransaction } from "../../types/liquidity";

const txn = (over: Partial<LiquidityTransaction> = {}): LiquidityTransaction => ({
  id: "t1",
  effective_date: "2026-04-20",
  description: "Rehab draw #2",
  amount_dollars: -12500,
  ...over,
});

function bucket(over: Partial<DayBucket> = {}): DayBucket {
  return {
    date: "2026-04-20",
    transactions: [txn()],
    net_dollars: -12500,
    balance_dollars: 36500,
    ...over,
  };
}

const mountDetail = (value: DayBucket | null = bucket()) =>
  mount(DayDetail, { props: { bucket: value } });

describe("DayDetail", () => {
  it("renders nothing without a selected day", () => {
    const wrapper = mountDetail(null);
    expect(wrapper.find('[data-testid="daydetail.root"]').exists()).toBe(false);
    expect(wrapper.text()).toBe("");
  });

  it("heads the panel with the selected date", () => {
    expect(mountDetail().text()).toContain("Apr 20, 2026");
  });

  it("says so when the day has no transactions", () => {
    const wrapper = mountDetail(bucket({ transactions: [], net_dollars: 0 }));
    expect(wrapper.find('[data-testid="daydetail.empty"]').text()).toBe(
      "No transactions on this date.",
    );
  });

  it("shows the day's net and end-of-day balance", () => {
    const text = mountDetail(bucket({ net_dollars: 4250, balance_dollars: -3500 })).text();
    expect(text).toContain("+$4,250");
    expect(text).toContain("-$3,500");
  });

  it("signs each row's amount", () => {
    const wrapper = mountDetail(
      bucket({
        transactions: [
          txn({ id: "out", amount_dollars: -12500 }),
          txn({ id: "in", amount_dollars: 8000, description: "Rent" }),
        ],
      }),
    );

    expect(wrapper.find('[data-testid="daydetail.txn.out"]').text()).toContain(
      "-$12,500",
    );
    expect(wrapper.find('[data-testid="daydetail.txn.in"]').text()).toContain(
      "+$8,000",
    );
  });

  it("marks a row projected from a recurring rule", () => {
    const wrapper = mountDetail(
      bucket({
        transactions: [
          txn({ id: "virtual", recurring_rule_id: "rule-1", recurring_index: 3 }),
        ],
      }),
    );

    const row = wrapper.find('[data-testid="daydetail.txn.virtual"]');
    expect(row.text()).toContain("recurring");
    expect(
      wrapper.find('[data-testid="daydetail.txn.virtual.edit"]').attributes("title"),
    ).toBe("Edit recurring series");
    expect(
      wrapper
        .find('[data-testid="daydetail.txn.virtual.delete"]')
        .attributes("title"),
    ).toBe("Delete recurring series");
  });

  describe("what it asks the page to do", () => {
    it("emits addOnDate with the day being viewed", async () => {
      const wrapper = mountDetail(bucket({ date: "2026-07-04" }));
      await wrapper.find('[data-testid="daydetail.add"]').trigger("click");
      expect(wrapper.emitted("addOnDate")).toEqual([["2026-07-04"]]);
    });

    it("emits editTxn with the row's id", async () => {
      const wrapper = mountDetail(
        bucket({ transactions: [txn({ id: "txn-42" })] }),
      );
      await wrapper.find('[data-testid="daydetail.txn.txn-42.edit"]').trigger("click");
      expect(wrapper.emitted("editTxn")).toEqual([["txn-42"]]);
    });

    it("emits deleteTxn with the row's id", async () => {
      const wrapper = mountDetail(
        bucket({ transactions: [txn({ id: "txn-42" })] }),
      );
      await wrapper
        .find('[data-testid="daydetail.txn.txn-42.delete"]')
        .trigger("click");
      expect(wrapper.emitted("deleteTxn")).toEqual([["txn-42"]]);
    });

    it("passes the instance id for a recurring row, leaving the page to resolve the rule", async () => {
      const wrapper = mountDetail(
        bucket({
          transactions: [txn({ id: "rule-1__2", recurring_rule_id: "rule-1" })],
        }),
      );
      await wrapper
        .find('[data-testid="daydetail.txn.rule-1__2.edit"]')
        .trigger("click");
      expect(wrapper.emitted("editTxn")).toEqual([["rule-1__2"]]);
    });
  });
});

describe("DayDetail — the quick row actions", () => {
  it("tags an overdue row and forwards Done, a move and an amount change", async () => {
    const overdue = txn({ effective_date: "2026-04-20", overdue_since_date: "2026-04-01" });
    const wrapper = mountDetail(bucket({ transactions: [overdue] }));
    expect(wrapper.find('[data-testid="daydetail.txn.t1.overdue"]').text()).toBe("overdue since Apr 1, 2026");
    await wrapper.find('[data-testid="rowactions.t1.done"]').trigger("click");
    await wrapper.find('[data-testid="rowactions.t1.date"]').setValue("2026-05-01");
    await wrapper.find('[data-testid="amount.t1"]').trigger("click");
    await wrapper.find('[data-testid="amount.t1.input"]').setValue("10000");
    await wrapper.find('[data-testid="amount.t1.input"]').trigger("keydown", { key: "Enter" });
    expect(wrapper.emitted("markDone")).toEqual([["t1"]]);
    expect(wrapper.emitted("moveToDate")).toEqual([["t1", "2026-05-01"]]);
    expect(wrapper.emitted("changeAmount")).toEqual([["t1", -10000]]);
  });
});
