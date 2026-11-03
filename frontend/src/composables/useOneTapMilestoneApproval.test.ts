import { describe, expect, it, vi } from "vitest";

import type { DealCashRowChanges, ImportedLiquidityDeal } from "../types/liquidity";
import { milestoneApprovalChangesSomething, useOneTapMilestoneApproval } from "./useOneTapMilestoneApproval";

const DEAL: ImportedLiquidityDeal = {
  deal_board: "my_deals", deal_id: "deal-1", deal_address: "1 Main St", my_deals_deal_id_it_was_moved_from: null,
  liquidity_rows_out_of_date: false, open_row_count: 3, done_row_count: 0, overdue_open_row_count: 0, late_refi_row_count: 0, refi_is_late: false,
  milestones: [{ milestone: "contract_signed", planned_date: "2026-08-20", approved_at: null, is_overdue: true }],
};

function preview(counts: Partial<DealCashRowChanges["change_counts"]> = {}, milestoneDateChanges: DealCashRowChanges["milestone_date_changes"] = []): DealCashRowChanges {
  return {
    deal_board: "my_deals", deal_id: "deal-1", deal_address: "1 Main St", changes: [],
    change_counts: { added: 0, updated: 0, removed: 0, unchanged: 5, kept_done: 0, kept_no_longer_in_the_deal: 0, conflicts_with_your_changes: 0, ...counts },
    milestone_date_changes: milestoneDateChanges,
  };
}

function setUp(previewResult: DealCashRowChanges | Error) {
  const dependencies = {
    previewMilestoneChange: vi.fn(() => (previewResult instanceof Error ? Promise.reject(previewResult) : Promise.resolve(previewResult))),
    applyMilestoneChange: vi.fn(() => Promise.resolve(preview())),
    openMilestoneApprovalReview: vi.fn(),
    showToast: vi.fn(),
  };
  return { dependencies, approval: useOneTapMilestoneApproval(dependencies) };
}

describe("useOneTapMilestoneApproval", () => {
  it("approves on the planned date at once when nothing else changes", async () => {
    const { dependencies, approval } = setUp(preview());
    await approval.approveMilestoneOnItsPlannedDate(DEAL, "contract_signed");
    const expectedRequest = { milestone: "contract_signed", new_date: "2026-08-20", approve: true, use_deal_value_for: [] };
    expect(dependencies.previewMilestoneChange).toHaveBeenCalledWith("my_deals", "deal-1", expectedRequest);
    expect(dependencies.applyMilestoneChange).toHaveBeenCalledWith("my_deals", "deal-1", expectedRequest);
    expect(dependencies.openMilestoneApprovalReview).not.toHaveBeenCalled();
    expect(dependencies.showToast).toHaveBeenCalledWith("Contract signed done.");
    expect(approval.milestoneKeyBeingApproved.value).toBeNull();
  });

  it("opens the before -> after list instead when a row would change, and applies nothing", async () => {
    const { dependencies, approval } = setUp(preview({ updated: 2 }));
    await approval.approveMilestoneOnItsPlannedDate(DEAL, "contract_signed");
    expect(dependencies.openMilestoneApprovalReview).toHaveBeenCalledWith(DEAL, "contract_signed");
    expect(dependencies.applyMilestoneChange).not.toHaveBeenCalled();
  });

  it("says so in a toast when the preview fails", async () => {
    const { dependencies, approval } = setUp(Object.assign(new Error("boom"), { response: { data: { detail: "Dates out of order" } } }));
    await approval.approveMilestoneOnItsPlannedDate(DEAL, "contract_signed");
    expect(dependencies.showToast).toHaveBeenCalledWith("Error: Dates out of order");
    expect(dependencies.applyMilestoneChange).not.toHaveBeenCalled();
  });
});

describe("milestoneApprovalChangesSomething", () => {
  it("is false only when no row is written, no milestone moves and nothing conflicts", () => {
    expect(milestoneApprovalChangesSomething(preview())).toBe(false);
    expect(milestoneApprovalChangesSomething(preview({ added: 1 }))).toBe(true);
    expect(milestoneApprovalChangesSomething(preview({ removed: 1 }))).toBe(true);
    expect(milestoneApprovalChangesSomething(preview({ kept_no_longer_in_the_deal: 1 }))).toBe(true);
    expect(milestoneApprovalChangesSomething(preview({ conflicts_with_your_changes: 1 }))).toBe(true);
    expect(milestoneApprovalChangesSomething(preview({}, [{ milestone: "rehab_completed", date_before: "2026-10-01", date_after: "2026-10-05" }]))).toBe(true);
  });
});
