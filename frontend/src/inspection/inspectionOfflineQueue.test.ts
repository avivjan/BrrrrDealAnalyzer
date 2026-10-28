// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";

import { mergePendingItemChange, pendingChangeAfterSent, readPendingItemChanges, writePendingItemChanges } from "./inspectionOfflineQueue";
import { MAXIMUM_RECENT_INSPECTIONS_ON_DEVICE, forgetInspectionOnDevice, readRecentInspectionsOnDevice, rememberInspectionOnDevice } from "./inspectionRecentOnDevice";

beforeEach(() => window.localStorage.clear());

describe("pending item changes", () => {
  it("merges two edits of one item: later values win, field values merge key by key", () => {
    const merged = mergePendingItemChange(
      { item_status: "ok", item_field_values: { supply_pipe_material: "pex" } },
      { item_status: "repair", item_field_values: { drain_pipe_material: "pvc" } },
    );
    expect(merged).toEqual({ item_status: "repair", item_field_values: { supply_pipe_material: "pex", drain_pipe_material: "pvc" } });
  });

  it("keeps edits made while a request was in flight, and drops what the server now has", () => {
    const sent = { item_status: "ok" as const, item_field_values: { sewer_type: "septic" } };
    const current = { item_status: "ok" as const, item_field_values: { sewer_type: "septic", septic_last_pump_date: "2024-01-01" } };
    expect(pendingChangeAfterSent(current, sent)).toEqual({ item_field_values: { septic_last_pump_date: "2024-01-01" } });
    expect(pendingChangeAfterSent(sent, sent)).toBeUndefined();
    expect(pendingChangeAfterSent({ item_notes: "leak", item_status: "repair" }, { item_notes: "lea", item_status: "repair" })).toEqual({ item_notes: "leak" });
  });

  it("survives a reload through localStorage, and clears the key once empty", () => {
    writePendingItemChanges("inspection-1", { roof: { item_status: "ok" } });
    expect(readPendingItemChanges("inspection-1")).toEqual({ roof: { item_status: "ok" } });
    writePendingItemChanges("inspection-1", {});
    expect(window.localStorage.getItem("bw.inspection.pendingChanges.inspection-1")).toBeNull();
  });

  it("ignores corrupt stored data", () => {
    window.localStorage.setItem("bw.inspection.pendingChanges.inspection-1", "not json");
    expect(readPendingItemChanges("inspection-1")).toEqual({});
  });
});

describe("recent inspections on this device", () => {
  it("keeps the most recently opened first, without duplicates, at most 20", () => {
    for (let index = 0; index < MAXIMUM_RECENT_INSPECTIONS_ON_DEVICE + 3; index += 1) {
      rememberInspectionOnDevice({ inspection_id: `inspection-${index}`, property_address: `${index} Palm Ave`, inspection_date: "2026-10-28" });
    }
    rememberInspectionOnDevice({ inspection_id: "inspection-5", property_address: "5 Palm Ave", inspection_date: "2026-10-28" });
    const recent = readRecentInspectionsOnDevice();
    expect(recent).toHaveLength(MAXIMUM_RECENT_INSPECTIONS_ON_DEVICE);
    expect(recent[0]!.inspection_id).toBe("inspection-5");
    expect(recent.filter((entry) => entry.inspection_id === "inspection-5")).toHaveLength(1);
  });

  it("forgets a deleted inspection and tolerates corrupt storage", () => {
    rememberInspectionOnDevice({ inspection_id: "keep", property_address: "1 Bay St", inspection_date: "2026-10-28" });
    rememberInspectionOnDevice({ inspection_id: "drop", property_address: "2 Bay St", inspection_date: "2026-10-28" });
    expect(forgetInspectionOnDevice("drop").map((entry) => entry.inspection_id)).toEqual(["keep"]);
    window.localStorage.setItem("bw.inspections.recentOnDevice", "{\"not\": \"a list\"}");
    expect(readRecentInspectionsOnDevice()).toEqual([]);
  });
});
