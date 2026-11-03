// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";

import DayTransactionsModal from "./DayTransactionsModal.vue";
import type { DayBucket, ImportedLiquidityDeal } from "../../../types/liquidity";

const DEAL: ImportedLiquidityDeal = {
  deal_board: "my_deals", deal_id: "d1", deal_address: "4431 Victor St, Jacksonville, FL 32207", my_deals_deal_id_it_was_moved_from: null,
  liquidity_rows_out_of_date: false, open_row_count: 3, done_row_count: 0, overdue_open_row_count: 0, late_refi_row_count: 0, refi_is_late: false,
  milestones: [{ milestone: "rehab_completed", planned_date: "2026-11-20", approved_at: null, is_overdue: false }],
};
const BUCKET: DayBucket = {
  date: "2026-11-20",
  transactions: [
    { id: "survey", effective_date: "2026-11-20", description: "Survey", amount_dollars: -385, source_deal_board: "my_deals", source_deal_id: "d1" },
    { id: "spread", effective_date: "2026-11-20", description: "Draw spread back", amount_dollars: 5665 },
  ],
  net_dollars: 5280,
  balance_dollars: 63903.23,
};

function mountModal(over: Partial<InstanceType<typeof DayTransactionsModal>["$props"]> = {}) {
  return mount(DayTransactionsModal, {
    props: {
      bucket: BUCKET, openingBalanceDollars: 58623.23, milestonesOnThisDay: [{ deal: DEAL, state: DEAL.milestones[0]! }],
      canStepToPreviousDay: true, canStepToNextDay: false, ...over,
    },
    attachTo: document.body,
  });
}

describe("DayTransactionsModal", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 10, 3, 12));
  });
  afterEach(() => vi.useRealTimers());

  it("heads the day with its long date and its four figures", () => {
    const wrapper = mountModal();
    expect(wrapper.get("h2").text()).toBe("Friday, November 20, 2026");
    const summary = wrapper.get('[data-testid="theater.day-modal.summary"]').text();
    expect(summary).toContain("$58,623.23");
    expect(wrapper.get('[data-testid="theater.day-modal.money-in"]').text()).toContain("5,665");
    expect(wrapper.get('[data-testid="theater.day-modal.money-out"]').text()).toContain("385");
    expect(wrapper.get('[data-testid="theater.day-modal.eod"]').text()).toContain("$63,903.23");
    wrapper.unmount();
  });

  it("lists the milestones planned that day, with Approve and Move", async () => {
    const wrapper = mountModal();
    const milestone = wrapper.get('[data-testid="theater.day-modal.milestone"]');
    expect(milestone.text()).toContain("Rehab completed");
    expect(milestone.text()).toContain("4431 Victor St");
    await milestone.get('[data-testid="theater.day-modal.milestone.approve"]').trigger("click");
    await milestone.get('[data-testid="theater.day-modal.milestone.move"]').trigger("click");
    expect(wrapper.emitted("approveMilestone")?.[0]).toEqual([DEAL, "rehab_completed"]);
    expect(wrapper.emitted("moveMilestone")?.[0]).toEqual([DEAL, "rehab_completed"]);
    wrapper.unmount();
  });

  it("carries every row's actions through to the view", async () => {
    const wrapper = mountModal();
    await wrapper.get('[data-testid="rowactions.survey.done"]').trigger("click");
    await wrapper.get('[data-testid="rowactions.survey.postpone.week"]').trigger("click");
    expect(wrapper.emitted("markDone")).toEqual([["survey"]]);
    expect(wrapper.emitted("moveToDate")).toEqual([["survey", "2026-11-27"]]);
    wrapper.unmount();
  });

  it("steps days with its buttons and the arrow keys, only where a day exists", async () => {
    const wrapper = mountModal();
    await wrapper.get('[data-testid="theater.day-modal.previous"]').trigger("click");
    expect(wrapper.get('[data-testid="theater.day-modal.next"]').attributes("disabled")).toBeDefined();
    await wrapper.get('[role="dialog"]').trigger("keydown", { key: "ArrowLeft" });
    await wrapper.get('[role="dialog"]').trigger("keydown", { key: "ArrowRight" });
    expect(wrapper.emitted("stepDay")).toEqual([[-1], [-1]]);
    wrapper.unmount();
  });

  it("closes on its × and on a click outside the panel", async () => {
    const wrapper = mountModal();
    await wrapper.get('[data-testid="theater.day-modal.close"]').trigger("click");
    await wrapper.get('[data-testid="theater.day-modal"]').trigger("click");
    expect(wrapper.emitted("close")).toHaveLength(2);
    wrapper.unmount();
  });
});
