// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount, RouterLinkStub } from "@vue/test-utils";

import LiquidityDealsPanel from "./LiquidityDealsPanel.vue";
import type { ImportedLiquidityDeal, LiquidityTransaction } from "../../types/liquidity";

const DEAL: ImportedLiquidityDeal = {
  deal_board: "my_deals", deal_id: "deal-1", deal_address: "1 Main St", my_deals_deal_id_it_was_moved_from: null,
  liquidity_rows_out_of_date: true, open_row_count: 2, done_row_count: 1, overdue_open_row_count: 1, late_refi_row_count: 0, refi_is_late: false,
  milestones: [
    { milestone: "contract_signed", planned_date: "2026-01-03", approved_at: "2026-01-03T12:00:00Z", is_overdue: false },
    { milestone: "purchase_closed", planned_date: "2026-01-10", approved_at: null, is_overdue: true },
    { milestone: "rehab_completed", planned_date: "2026-02-24", approved_at: null, is_overdue: false },
    { milestone: "tenant_moved_in", planned_date: "2026-04-10", approved_at: null, is_overdue: false },
    { milestone: "refi_closed", planned_date: "2026-07-09", approved_at: null, is_overdue: false },
  ],
};

const TRANSACTIONS: LiquidityTransaction[] = [
  { id: "a", effective_date: "2026-01-10", description: "Cash to close", amount_dollars: -50000, source_deal_id: "deal-1" },
  { id: "b", effective_date: "2026-01-03", description: "Earnest money deposit", amount_dollars: -5000, source_deal_id: "deal-1", done_at: "2026-01-03T00:00:00Z" },
  { id: "c", effective_date: "2026-01-12", description: "Groceries", amount_dollars: -200 },
];

function mountPanel() {
  return mount(LiquidityDealsPanel, {
    props: { importedDeals: [DEAL], transactions: TRANSACTIONS },
    global: { stubs: { RouterLink: RouterLinkStub } },
  });
}

describe("LiquidityDealsPanel", () => {
  it("is hidden with no imported deal", () => {
    const wrapper = mount(LiquidityDealsPanel, { props: { importedDeals: [], transactions: [] }, global: { stubs: { RouterLink: RouterLinkStub } } });
    expect(wrapper.find('[data-testid="liquidity-deals"]').exists()).toBe(false);
  });

  it("shows each milestone's state and offers Approve only while it is not approved", () => {
    const milestones = mountPanel().findAll('[data-testid="liquidity-deal.milestone"]');
    expect(milestones[0]!.text()).toContain("approved");
    expect(milestones[0]!.find('[data-testid="liquidity-deal.milestone.approve"]').exists()).toBe(false);
    expect(milestones[1]!.text()).toContain("overdue");
    expect(milestones[1]!.find('[data-testid="liquidity-deal.milestone.approve"]').exists()).toBe(true);
  });

  it("emits the milestone actions, Review changes and the dead-deal cleanup", async () => {
    const wrapper = mountPanel();
    await wrapper.findAll('[data-testid="liquidity-deal.milestone.approve"]')[0]!.trigger("click");
    await wrapper.findAll('[data-testid="liquidity-deal.milestone.move"]')[4]!.trigger("click");
    expect(wrapper.emitted("changeMilestone")).toEqual([[DEAL, "purchase_closed", true], [DEAL, "refi_closed", false]]);
    await wrapper.get('[data-testid="liquidity-deal.review-changes"]').trigger("click");
    expect(wrapper.emitted("reviewChanges")).toEqual([[DEAL]]);
    await wrapper.get('[data-testid="liquidity-deal.remove-open-rows"]').trigger("click");
    expect(wrapper.emitted("removeOpenRows")).toEqual([[DEAL]]);
  });

  it("lists only the deal's open rows when filtered on it", async () => {
    const wrapper = mountPanel();
    await wrapper.get('[data-testid="liquidity-deal.toggle-rows"]').trigger("click");
    const rows = wrapper.get('[data-testid="liquidity-deal.rows"]').text();
    expect(rows).toContain("Cash to close");
    expect(rows).not.toContain("Earnest money deposit");
    expect(rows).not.toContain("Groceries");
  });
});
