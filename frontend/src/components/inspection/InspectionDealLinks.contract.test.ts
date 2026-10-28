// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";

import DealLinkedInspectionsSection from "./DealLinkedInspectionsSection.vue";
import InspectionDealLinkDrawer from "./InspectionDealLinkDrawer.vue";

const { getActiveDeals, getBoughtDeals, inspectionApi } = vi.hoisted(() => ({
  getActiveDeals: vi.fn(),
  getBoughtDeals: vi.fn(),
  inspectionApi: {
    getInspectionDealLink: vi.fn(),
    linkInspectionToDeal: vi.fn(),
    unlinkInspectionFromDeal: vi.fn(),
    listDealInspections: vi.fn(),
    createInspectionForDeal: vi.fn(),
    getInspection: vi.fn(),
  },
}));
vi.mock("../../api", () => ({
  default: { getActiveDeals: () => getActiveDeals(), getBoughtDeals: () => getBoughtDeals() },
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));
vi.mock("../../api/inspection", () => ({ inspectionApi }));
vi.mock("vue-router", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const INSPECTION_ID = "3f2a9c1e-0000-4000-8000-000000000001";

beforeEach(() => {
  setActivePinia(createPinia());
  for (const mock of [getActiveDeals, getBoughtDeals, ...Object.values(inspectionApi)]) mock.mockReset();
  getActiveDeals.mockResolvedValue([{ id: "active-1", address: "12 Palm Ave", deal_type: "BRRRR" }]);
  getBoughtDeals.mockResolvedValue([{ id: "bought-1", address: "9 Bay St", deal_type: "FLIP" }]);
  inspectionApi.getInspectionDealLink.mockResolvedValue({ linked_deal: null });
  inspectionApi.linkInspectionToDeal.mockImplementation(async (_id, deal_board, deal_id, deal_type) => ({
    linked_deal: { deal_board, deal_id, deal_type, property_address: "12 Palm Ave" },
  }));
});

describe("InspectionDealLinkDrawer", () => {
  it("starts on My Deals, links a My Deals deal, and can switch to Bought", async () => {
    mount(InspectionDealLinkDrawer, { props: { inspectionId: INSPECTION_ID }, attachTo: document.body });
    await flushPromises();
    expect(getActiveDeals).toHaveBeenCalledTimes(1);
    expect(getBoughtDeals).not.toHaveBeenCalled();

    document.body.querySelector<HTMLButtonElement>('[data-testid="inspection.deal-link.deal.active-1"]')!.click();
    await flushPromises();
    expect(inspectionApi.linkInspectionToDeal).toHaveBeenCalledWith(INSPECTION_ID, "my_deals", "active-1", "BRRRR");
    expect(document.body.textContent).toContain("Linked to · My Deals");

    const boughtTab = [...document.body.querySelectorAll<HTMLButtonElement>('[data-testid="inspection.deal-link.board"] [role="radio"]')].find((radio) => radio.textContent?.includes("Bought"))!;
    boughtTab.click();
    await flushPromises();
    expect(getBoughtDeals).toHaveBeenCalledTimes(1);
    expect(document.body.querySelector('[data-testid="inspection.deal-link.deal.bought-1"]')).not.toBeNull();
    document.body.innerHTML = "";
  });

  it("opens on the board of the current link", async () => {
    inspectionApi.getInspectionDealLink.mockResolvedValue({ linked_deal: { deal_board: "bought", deal_id: "bought-1", deal_type: "FLIP", property_address: "9 Bay St" } });
    mount(InspectionDealLinkDrawer, { props: { inspectionId: INSPECTION_ID }, attachTo: document.body });
    await flushPromises();
    expect(getBoughtDeals).toHaveBeenCalledTimes(1);
    expect(document.body.querySelector<HTMLButtonElement>('[data-testid="inspection.deal-link.deal.bought-1"]')!.disabled).toBe(true);
    document.body.innerHTML = "";
  });
});

describe("DealLinkedInspectionsSection", () => {
  it.each([
    ["my_deals", "mydeals.modal"],
    ["bought", "boughtdeals.modal"],
  ] as const)("lists and starts inspections for a %s deal", async (dealBoard, testIdPrefix) => {
    inspectionApi.listDealInspections.mockResolvedValue([]);
    inspectionApi.createInspectionForDeal.mockResolvedValue({ id: INSPECTION_ID, property_address: "12 Palm Ave", inspection_date: "2026-10-28" });
    const wrapper = mount(DealLinkedInspectionsSection, { props: { dealBoard, dealId: "deal-1", dealType: "BRRRR", testIdPrefix } });
    await flushPromises();
    expect(inspectionApi.listDealInspections).toHaveBeenCalledWith(dealBoard, "deal-1", "BRRRR");
    expect(wrapper.find(`[data-testid="${testIdPrefix}.inspections"]`).exists()).toBe(true);
    await wrapper.get(`[data-testid="${testIdPrefix}.inspections.new"]`).trigger("click");
    await flushPromises();
    expect(inspectionApi.createInspectionForDeal).toHaveBeenCalledWith(dealBoard, "deal-1", "BRRRR");
  });
});
