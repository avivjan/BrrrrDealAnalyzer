// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import DealMilestonesBottomSheet from "./DealMilestonesBottomSheet.vue";
import type { ImportedLiquidityDeal } from "../../../types/liquidity";

const DEAL: ImportedLiquidityDeal = {
  deal_board: "bought", deal_id: "d1", deal_address: "4431 Victor St, Jacksonville, FL 32207", my_deals_deal_id_it_was_moved_from: null,
  liquidity_rows_out_of_date: false, open_row_count: 15, done_row_count: 0, overdue_open_row_count: 5, late_refi_row_count: 0, refi_is_late: false,
  milestones: [
    { milestone: "purchase_closed", planned_date: "2026-10-29", approved_at: "2026-10-29T12:00:00Z", is_overdue: false },
    { milestone: "contract_signed", planned_date: "2026-10-21", approved_at: "2026-10-21T12:00:00Z", is_overdue: false },
    { milestone: "rehab_completed", planned_date: "2026-11-20", approved_at: null, is_overdue: false },
    { milestone: "tenant_moved_in", planned_date: "2027-01-01", approved_at: null, is_overdue: true },
    { milestone: "refi_closed", planned_date: "2027-01-01", approved_at: null, is_overdue: false },
  ],
};
const REMOVED_DEAL: ImportedLiquidityDeal = { ...DEAL, deal_id: "d2", deal_address: "Gone St", open_row_count: 0 };

function mountSheet(open = true) {
  return mount(DealMilestonesBottomSheet, { props: { importedDeals: [DEAL, REMOVED_DEAL], open } });
}

describe("DealMilestonesBottomSheet", () => {
  it("has one card per deal still in the timeline, its milestones in date order", () => {
    const cards = mountSheet().findAll('[data-testid="theater.sheet.deal"]');
    expect(cards).toHaveLength(1);
    expect(cards[0]!.text()).toContain("4431 Victor St");
    expect(cards[0]!.findAll('[data-testid="theater.sheet.milestone"]').map((item) => item.attributes("data-milestone"))).toEqual([
      "contract_signed", "purchase_closed", "rehab_completed", "tenant_moved_in", "refi_closed",
    ]);
  });

  it("mutes a done milestone and offers Done only on the open ones", () => {
    const milestones = mountSheet().findAll('[data-testid="theater.sheet.milestone"]');
    expect(milestones[0]!.attributes("data-done")).toBe("true");
    expect(milestones[0]!.classes()).toContain("opacity-50");
    expect(milestones[0]!.find('[data-testid="theater.sheet.milestone.done"]').exists()).toBe(false);
    expect(milestones[2]!.find('[data-testid="theater.sheet.milestone.done"]').exists()).toBe(true);
  });

  it("emits Done and Move with the deal and the milestone", async () => {
    const wrapper = mountSheet();
    const rehab = wrapper.findAll('[data-testid="theater.sheet.milestone"]')[2]!;
    await rehab.get('[data-testid="theater.sheet.milestone.done"]').trigger("click");
    await rehab.get('[data-testid="theater.sheet.milestone.move"]').trigger("click");
    expect(wrapper.emitted("approveMilestone")?.[0]).toEqual([DEAL, "rehab_completed"]);
    expect(wrapper.emitted("moveMilestone")?.[0]).toEqual([DEAL, "rehab_completed"]);
  });

  it("offers Done on another date on an open milestone only", async () => {
    const wrapper = mountSheet();
    const milestones = wrapper.findAll('[data-testid="theater.sheet.milestone"]');
    expect(milestones[0]!.find('[data-testid="theater.sheet.milestone.done-on-date"]').exists()).toBe(false);
    await milestones[2]!.get('[data-testid="theater.sheet.milestone.done-on-date"]').trigger("click");
    expect(wrapper.emitted("approveMilestoneOnAnotherDate")?.[0]).toEqual([DEAL, "rehab_completed"]);
  });

  it("is a collapsed bar that toggles the sheet, counting the overdue milestones", async () => {
    const wrapper = mountSheet(false);
    expect(wrapper.get('[data-testid="theater.sheet"]').attributes("aria-hidden")).toBe("true");
    const bar = wrapper.get('[data-testid="theater.sheet.toggle"]');
    expect(bar.attributes("aria-expanded")).toBe("false");
    expect(wrapper.get('[data-testid="theater.sheet.overdue-count"]').text()).toBe("1 overdue milestone");
    await bar.trigger("click");
    expect(wrapper.emitted("toggle")).toHaveLength(1);
  });
});
