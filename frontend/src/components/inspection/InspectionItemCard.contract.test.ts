// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { mount } from "@vue/test-utils";

import InspectionItemCard from "./InspectionItemCard.vue";
import { findChecklistItem } from "../../inspection/inspectionChecklistLogic";
import { useInspectionStore } from "../../stores/inspectionStore";

const updateInspectionItem = vi.fn();
vi.mock("../../api/inspection", () => ({
  inspectionApi: {
    updateInspectionItem: (...args: unknown[]) => updateInspectionItem(...args),
    getInspection: vi.fn(),
    uploadInspectionPhoto: vi.fn(),
  },
}));

const INSPECTION_ID = "3f2a9c1e-0000-4000-8000-000000000001";

function mountCard(itemKey: string) {
  const store = useInspectionStore();
  store.inspection = {
    id: INSPECTION_ID,
    property_address: "12 Palm Ave",
    inspection_date: "2026-10-28",
    inspector_name: null,
    inspection_status: "draft",
    completed_at: null,
    completion_override_reason: null,
    linked: false,
    created_at: null,
    updated_at: null,
    items: [],
    photos: [],
  };
  const wrapper = mount(InspectionItemCard, { props: { item: findChecklistItem(itemKey)!, levelLabel: "Utilities & Mechanicals" } });
  return { wrapper, store };
}

const openFieldLegends = (wrapper: ReturnType<typeof mountCard>["wrapper"]) => wrapper.findAll("legend").map((legend) => legend.text());

beforeEach(() => {
  setActivePinia(createPinia());
  window.localStorage.clear();
  updateInspectionItem.mockReset();
  updateInspectionItem.mockResolvedValue({});
  vi.useFakeTimers();
});

describe("InspectionItemCard", () => {
  it("asks for the condition first, and nothing else", () => {
    const { wrapper } = mountCard("sewer");
    expect(wrapper.find('[data-testid="inspection.card.status.ok"]').exists()).toBe(true);
    expect(openFieldLegends(wrapper)).toEqual([]);
    expect(wrapper.find('[data-testid="inspection.card.critical"]').exists()).toBe(true);
  });

  it("reveals the sewer type after the status, and the septic pump date only after Septic", async () => {
    const { wrapper } = mountCard("sewer");
    await wrapper.get('[data-testid="inspection.card.status.ok"]').trigger("click");
    expect(openFieldLegends(wrapper)).toEqual(["Sewer type"]);
    await wrapper.get('[data-testid="inspection.field.sewer_type.city"]').trigger("click");
    expect(openFieldLegends(wrapper)).toEqual([]); // City: no follow-up, straight to photos and notes
    expect(wrapper.find('[data-testid="inspection.card.notes"]').exists()).toBe(true);

    await wrapper.get('[data-testid="inspection.card.answer.sewer_type"]').trigger("click");
    await wrapper.get('[data-testid="inspection.field.sewer_type.septic"]').trigger("click");
    expect(openFieldLegends(wrapper)).toEqual(["Last septic pump date"]);
  });

  it("asks about the well pump only for a well", async () => {
    const { wrapper } = mountCard("water_supply");
    await wrapper.get('[data-testid="inspection.card.status.repair"]').trigger("click");
    await wrapper.get('[data-testid="inspection.field.water_supply_type.well"]').trigger("click");
    expect(openFieldLegends(wrapper)).toEqual(["Well pump & filtration condition"]);
  });

  it("saves each answer as one merged PATCH of this item after a short pause", async () => {
    const { wrapper, store } = mountCard("sewer");
    await wrapper.get('[data-testid="inspection.card.status.repair"]').trigger("click");
    await wrapper.get('[data-testid="inspection.field.sewer_type.septic"]').trigger("click");
    expect(store.pendingChangeCount).toBe(1);
    expect(updateInspectionItem).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(700);
    expect(updateInspectionItem).toHaveBeenCalledTimes(1);
    expect(updateInspectionItem).toHaveBeenCalledWith(INSPECTION_ID, "sewer", { item_status: "repair", item_field_values: { sewer_type: "septic" } });
    expect(store.pendingChangeCount).toBe(0);
  });

  it("keeps a change queued when the network is down, and sends it later", async () => {
    updateInspectionItem.mockRejectedValueOnce(new Error("Network Error"));
    const { wrapper, store } = mountCard("roof");
    await wrapper.get('[data-testid="inspection.card.status.ok"]').trigger("click");
    await vi.advanceTimersByTimeAsync(700);
    expect(store.saveState).toBe("offline");
    expect(store.pendingChangeCount).toBe(1);
    expect(JSON.parse(window.localStorage.getItem(`bw.inspection.pendingChanges.${INSPECTION_ID}`)!)).toEqual({ roof: { item_status: "ok" } });
    await store.flushPendingChanges();
    expect(updateInspectionItem).toHaveBeenCalledTimes(2);
    expect(store.pendingChangeCount).toBe(0);
  });
});
