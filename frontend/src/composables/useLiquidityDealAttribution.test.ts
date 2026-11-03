// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { defineComponent, h, ref } from "vue";

import DayDetail from "../components/liquidity/DayDetail.vue";
import OverdueTransactionsStrip from "../components/liquidity/OverdueTransactionsStrip.vue";
import DealAttributionTag from "../components/liquidity/DealAttributionTag.vue";
import type { ImportedLiquidityDeal, LiquidityTransaction } from "../types/liquidity";
import { buildDealAttributionLookup, dealAccentStyleForTransaction, provideLiquidityDealAttribution } from "./useLiquidityDealAttribution";

const deal = (over: Partial<ImportedLiquidityDeal>): ImportedLiquidityDeal => ({
  deal_board: "my_deals", deal_id: "deal-1", deal_address: "4431 Victor St, Jacksonville, FL 32207", my_deals_deal_id_it_was_moved_from: null,
  liquidity_rows_out_of_date: false, open_row_count: 3, done_row_count: 0, overdue_open_row_count: 0, late_refi_row_count: 0,
  refi_is_late: false, milestones: [], ...over,
});
const row = (over: Partial<LiquidityTransaction>): LiquidityTransaction => ({
  id: "t1", effective_date: "2026-09-04", description: "Rehab cushion", amount_dollars: -5000, ...over,
});

describe("buildDealAttributionLookup", () => {
  it("maps an imported row to its deal's address and color", () => {
    const lookup = buildDealAttributionLookup([deal({})], "dark");
    const attribution = lookup.attributionForTransaction(row({ source_deal_board: "my_deals", source_deal_id: "deal-1" }));
    expect(attribution?.dealAddress).toBe("4431 Victor St, Jacksonville, FL 32207");
    expect(attribution?.shortDealAddress).toBe("4431 Victor St");
    expect(attribution?.dealColorHex).toMatch(/^#[0-9a-f]{6}$/);
  });

  it("keeps the address and color of a done row whose deal has no open row left", () => {
    const lookup = buildDealAttributionLookup([deal({ open_row_count: 0, done_row_count: 4 })], "light");
    const doneRow = row({ source_deal_board: "my_deals", source_deal_id: "deal-1", done_at: "2026-09-01T00:00:00Z" });
    expect(lookup.attributionForTransaction(doneRow)?.shortDealAddress).toBe("4431 Victor St");
  });

  it("has no deal for a manual row, a recurring occurrence, or a deal it does not know", () => {
    const lookup = buildDealAttributionLookup([deal({})], "dark");
    expect(lookup.attributionForTransaction(row({}))).toBeNull();
    expect(lookup.attributionForTransaction(row({ recurring_rule_id: "r", source_deal_board: "my_deals", source_deal_id: "deal-1" }))).toBeNull();
    expect(lookup.attributionForTransaction(row({ source_deal_board: "bought", source_deal_id: "deal-1" }))).toBeNull();
  });

  it("gives a row its deal's left accent, and a manual row none", () => {
    const lookup = buildDealAttributionLookup([deal({})], "dark");
    const color = lookup.attributionForDealKey("my_deals:deal-1")!.dealColorHex;
    expect(dealAccentStyleForTransaction(lookup, row({ source_deal_board: "my_deals", source_deal_id: "deal-1" }))).toEqual({ boxShadow: `inset 3px 0 0 ${color}` });
    expect(dealAccentStyleForTransaction(lookup, row({}))).toEqual({});
    expect(dealAccentStyleForTransaction(null, row({ source_deal_board: "my_deals", source_deal_id: "deal-1" }))).toEqual({});
  });
});

describe("DealAttributionTag", () => {
  it("shows nothing when no lookup is provided", () => {
    const wrapper = mount(DealAttributionTag, { props: { txn: row({ source_deal_board: "my_deals", source_deal_id: "deal-1" }) } });
    expect(wrapper.find('[data-testid="deal-tag.t1"]').exists()).toBe(false);
  });

  it("shows the deal's street address and color when the view provides the lookup", () => {
    const Host = defineComponent({
      setup() {
        provideLiquidityDealAttribution(ref([deal({})]));
        return () => h(DealAttributionTag, { txn: row({ source_deal_board: "my_deals", source_deal_id: "deal-1" }) });
      },
    });
    const tag = mount(Host).get('[data-testid="deal-tag.t1"]');
    expect(tag.text()).toBe("4431 Victor St");
    expect(tag.attributes("title")).toBe("From 4431 Victor St, Jacksonville, FL 32207");
    expect(tag.find("span[aria-hidden]").attributes("style")).toContain("background-color");
  });
});

describe("the row components with the view's deal lookup", () => {
  const dealRow = row({ id: "cushion", source_deal_board: "my_deals", source_deal_id: "deal-1", effective_date: "2026-09-01" });
  const manualRow = row({ id: "utilities", description: "Utilities", amount_dollars: -80, effective_date: "2026-09-01" });
  const withLookup = (render: () => ReturnType<typeof h>) => defineComponent({
    setup() {
      provideLiquidityDealAttribution(ref([deal({})]));
      return render;
    },
  });

  it("DayDetail tags a deal row with its deal and gives it the deal's accent; a manual row gets neither", () => {
    const wrapper = mount(withLookup(() => h(DayDetail, {
      bucket: { date: "2026-09-01", transactions: [dealRow, manualRow], net_dollars: -5080, balance_dollars: 1000 },
    })));
    expect(wrapper.get('[data-testid="deal-tag.cushion"]').text()).toBe("4431 Victor St");
    expect(wrapper.get('[data-testid="daydetail.txn.cushion"]').attributes("style")).toContain("box-shadow");
    expect(wrapper.find('[data-testid="deal-tag.utilities"]').exists()).toBe(false);
    expect(wrapper.get('[data-testid="daydetail.txn.utilities"]').attributes("style")).toBeUndefined();
  });

  it("the overdue strip tags each overdue row with its deal", async () => {
    const wrapper = mount(withLookup(() => h(OverdueTransactionsStrip, {
      overdueMoneyOut: [dealRow, manualRow], expectedMoneyInNotCounted: [], initiallyOpen: true,
    })));
    expect(wrapper.get('[data-testid="overdue.row.cushion"]').text()).toContain("4431 Victor St");
    expect(wrapper.find('[data-testid="deal-tag.utilities"]').exists()).toBe(false);
  });
});
