// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { nextTick } from "vue";

import ArvEstimateWithClaudePopup from "./ArvEstimateWithClaudePopup.vue";
import api from "../../api";
import type { ArvEstimateRes } from "../../types/arvEstimate";
import type { DealInputModel } from "../../types";

vi.mock("../../api", () => ({
  default: { estimateArvWithClaude: vi.fn() },
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

const estimateArvWithClaude = vi.mocked(api.estimateArvWithClaude);

const CLAUDE_ARV_ESTIMATE: ArvEstimateRes = {
  estimated_arv_range_low: 195000,
  estimated_arv_range_high: 215000,
  target_arv: 205000,
  conservative_lowest_arv: 190000,
  confidence_score_1_to_10: 7,
  average_days_on_market_of_sold_comparables: 22,
  median_days_on_market_of_sold_comparables: 18,
  market_pace_verdict: "NORMAL",
  market_logic: "Three renovated 3/2 sales within 0.3 mi carry the value.",
  subject_property_as_found: { bedrooms: 3, bathrooms: 1, square_feet: 1400, year_built: 1925, lot_size_square_feet: null, property_style: null },
  sold_comparables: [
    {
      address: "130 Main St",
      distance_from_subject_in_miles: 0.2,
      listing_status: "SOLD",
      sale_or_list_date: "2026-08-01",
      sale_or_list_price: 205000,
      bedrooms: 3,
      bathrooms: 2,
      square_feet: 1380,
      year_built: 1925,
      lot_size_square_feet: null,
      price_per_square_foot: 148.55,
      days_on_market: 18,
      renovation_condition: "Flip-grade renovated",
      adjusted_value_for_subject: 207000,
      adjustment_explanation: "+$2k for GLA",
      weight_in_valuation: "PRIMARY",
      source_url: "https://www.redfin.com/130-Main-St",
    },
  ],
  active_or_pending_comparables: [],
  discarded_comparables: [{ address: "9 Elm St", reason_for_discarding: "Sold as-is" }],
  data_caveats: ["Only three renovated sales in 6 months."],
  source_urls: ["https://www.redfin.com/130-Main-St"],
};

const DEAL_WITH_ADDRESS_AND_FACTS: DealInputModel = {
  address: "123 Main St, Cleveland, OH",
  sqft: 1400,
  bedrooms: 3,
  bathrooms: 1,
  purchasePrice: 90,
  rehabCost: 60,
};

let wrapper: VueWrapper | null = null;

beforeEach(() => {
  estimateArvWithClaude.mockReset();
});

afterEach(() => {
  wrapper?.unmount();
  wrapper = null;
  document.body.innerHTML = "";
});

function mountArvEstimatePopup(props: Record<string, unknown> = {}) {
  return mount(ArvEstimateWithClaudePopup, {
    attachTo: document.body,
    props: { isOpen: true, dealType: "BRRRR", deal: DEAL_WITH_ADDRESS_AND_FACTS, ...props },
  });
}

const byTestId = (testId: string) => document.querySelector(`[data-testid="${testId}"]`) as HTMLElement | null;

async function clickByTestId(testId: string) {
  byTestId(testId)!.click();
  await flushPromises();
}

describe("ArvEstimateWithClaudePopup", () => {
  it("renders nothing while closed", async () => {
    wrapper = mountArvEstimatePopup({ isOpen: false });
    await nextTick();
    expect(byTestId("arvEstimate.root")).toBeNull();
  });

  it("prefills the deal's address and names the strategy lens", async () => {
    wrapper = mountArvEstimatePopup({ dealType: "FLIP" });
    await nextTick();
    expect((byTestId("arvEstimate.address") as HTMLInputElement).value).toBe("123 Main St, Cleveland, OH");
    expect(byTestId("arvEstimate.strategy")!.textContent).toContain("Flip — conservative");
    expect(byTestId("arvEstimate.costNote")!.textContent).toContain("Each estimate costs roughly $0.10–0.50");
  });

  it("sends the address, the note and the deal's facts in dollars", async () => {
    estimateArvWithClaude.mockResolvedValue(CLAUDE_ARV_ESTIMATE);
    wrapper = mountArvEstimatePopup();
    await nextTick();
    const noteBox = byTestId("arvEstimate.note") as HTMLTextAreaElement;
    noteBox.value = "Full gut, adding a bathroom.";
    noteBox.dispatchEvent(new Event("input"));
    await clickByTestId("arvEstimate.submit");

    expect(estimateArvWithClaude).toHaveBeenCalledWith({
      deal_type: "BRRRR",
      property_address: "123 Main St, Cleveland, OH",
      investor_situation_note: "Full gut, adding a bathroom.",
      subject_square_feet: 1400,
      subject_bedrooms: 3,
      subject_bathrooms: 1,
      purchase_price: 90000,
      rehab_budget: 60000,
    });
  });

  it("renders the estimate: tiles, comps table, logic, caveats and safe links", async () => {
    estimateArvWithClaude.mockResolvedValue(CLAUDE_ARV_ESTIMATE);
    wrapper = mountArvEstimatePopup();
    await nextTick();
    await clickByTestId("arvEstimate.submit");

    expect(byTestId("arvEstimate.result.targetArv")!.textContent).toContain("$205,000");
    expect(byTestId("arvEstimate.result.range")!.textContent).toContain("$195,000 – $215,000");
    expect(byTestId("arvEstimate.result.confidence")!.textContent).toContain("7/10");
    expect(byTestId("arvEstimate.result.daysOnMarket")!.textContent).toContain("22 days");
    expect(byTestId("arvEstimate.result.daysOnMarket")!.textContent).toContain("Normal pace");
    expect(byTestId("arvEstimate.result.marketLogic")!.textContent).toContain("Three renovated");
    expect(byTestId("arvEstimate.result.caveats")!.textContent).toContain("Only three renovated sales");

    const soldTable = byTestId("arvEstimate.result.soldComparables")!;
    expect(soldTable.textContent).toContain("130 Main St");
    expect(soldTable.textContent).toContain("$149");
    const compLink = soldTable.querySelector("a")!;
    expect(compLink.getAttribute("href")).toBe("https://www.redfin.com/130-Main-St");
    expect(compLink.getAttribute("rel")).toBe("noopener noreferrer");
    expect(compLink.getAttribute("target")).toBe("_blank");
  });

  it("renders Claude's text as text, never as HTML", async () => {
    estimateArvWithClaude.mockResolvedValue({ ...CLAUDE_ARV_ESTIMATE, market_logic: '<img src=x onerror="alert(1)">' });
    wrapper = mountArvEstimatePopup();
    await nextTick();
    await clickByTestId("arvEstimate.submit");
    expect(byTestId("arvEstimate.result.marketLogic")!.querySelector("img")).toBeNull();
    expect(byTestId("arvEstimate.result.marketLogic")!.textContent).toContain("<img");
  });

  it("emits the estimate and closes on Apply", async () => {
    estimateArvWithClaude.mockResolvedValue(CLAUDE_ARV_ESTIMATE);
    wrapper = mountArvEstimatePopup();
    await nextTick();
    await clickByTestId("arvEstimate.submit");
    expect(byTestId("arvEstimate.apply")!.textContent).toContain("Apply to ARV and Lowest ARV");
    await clickByTestId("arvEstimate.apply");

    expect(wrapper.emitted("apply-arv-estimate")).toEqual([[CLAUDE_ARV_ESTIMATE]]);
    expect(wrapper.emitted("close")).toHaveLength(1);
  });

  it("shows the backend's message when the estimate fails", async () => {
    estimateArvWithClaude.mockImplementation(async () => {
      throw Object.assign(new Error("Request failed with status code 503"), {
        response: { data: { detail: "ARV estimate is not configured on the server." } },
      });
    });
    wrapper = mountArvEstimatePopup();
    await nextTick();
    await clickByTestId("arvEstimate.submit");
    expect(byTestId("arvEstimate.error")!.textContent).toContain("not configured");
    expect(byTestId("arvEstimate.apply")).toBeNull();
  });

  it("names the HTTP status when a failure carries no message (a proxy error page)", async () => {
    estimateArvWithClaude.mockImplementation(async () => {
      throw Object.assign(new Error("Request failed with status code 504"), { response: { status: 504, data: "<html>Gateway Timeout</html>" } });
    });
    wrapper = mountArvEstimatePopup();
    await nextTick();
    await clickByTestId("arvEstimate.submit");
    expect(byTestId("arvEstimate.error")!.textContent).toContain("The ARV estimate failed (HTTP 504); try again.");
  });

  it("asks for an address before calling Claude", async () => {
    wrapper = mountArvEstimatePopup({ deal: {} });
    await nextTick();
    await clickByTestId("arvEstimate.submit");
    expect(estimateArvWithClaude).not.toHaveBeenCalled();
    expect(byTestId("arvEstimate.error")!.textContent).toContain("address");
  });

  it("closes on Escape", async () => {
    wrapper = mountArvEstimatePopup();
    await nextTick();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(wrapper.emitted("close")).toHaveLength(1);
  });
});
