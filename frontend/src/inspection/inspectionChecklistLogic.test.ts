import { describe, expect, it } from "vitest";

import {
  INSPECTION_CHECKLIST_CONFIG,
  approximateAgeLabel,
  cardQuestionsOfItem,
  clampCounterValue,
  findChecklistItem,
  finishEligibility,
  formatFieldValue,
  inspectionShareText,
  isCompletionOverrideReasonAcceptable,
  levelProgress,
  neighbourItemKey,
  overallProgressFraction,
  remainingCriticalItems,
  revealedQuestionCount,
  visibleFieldsOfItem,
  type InspectionItemAnswers,
  type InspectionItemStatus,
} from "./inspectionChecklistLogic";

const CRITICAL_ITEM_KEYS = ["roof", "foundation", "hvac", "electrical", "plumbing", "water_heater", "sewer", "water_supply"];

function answered(item_status: InspectionItemStatus, item_field_values: InspectionItemAnswers["item_field_values"] = {}, item_notes: string | null = null): InspectionItemAnswers {
  return { item_status, item_field_values, item_notes };
}

function allCriticalItemsWithStatus(status: InspectionItemStatus): Record<string, InspectionItemAnswers> {
  return Object.fromEntries(CRITICAL_ITEM_KEYS.map((itemKey) => [itemKey, answered(status)]));
}

const sewer = findChecklistItem("sewer")!;
const waterSupply = findChecklistItem("water_supply")!;
const windows = findChecklistItem("windows")!;
const windowsCounterField = windows.fields[0]!;

describe("finish gating", () => {
  it("blocks finishing while any CRITICAL item is not checked, and names them", () => {
    const answers = allCriticalItemsWithStatus("ok");
    delete answers.hvac;
    delete answers.sewer;
    const eligibility = finishEligibility(answers);
    expect(eligibility.canFinish).toBe(false);
    expect(eligibility.needsOverrideReason).toBe(true);
    expect(eligibility.canFinish === false && eligibility.remainingCriticalItemLabels).toEqual(["HVAC", "Sewer"]);
  });

  it("allows finishing once every CRITICAL item has OK, Repair or Replace, whatever the other items say", () => {
    const answers = { ...allCriticalItemsWithStatus("repair"), roof: answered("replace") };
    expect(finishEligibility(answers)).toEqual({ canFinish: true, needsOverrideReason: false });
    expect(remainingCriticalItems(answers)).toEqual([]);
  });

  it("treats an item set back to Not checked as unchecked again", () => {
    const answers = { ...allCriticalItemsWithStatus("ok"), roof: answered("not_checked") };
    expect(finishEligibility(answers).canFinish).toBe(false);
  });

  it("accepts an override reason only at 10 characters or more", () => {
    expect(isCompletionOverrideReasonAcceptable("too short")).toBe(false);
    expect(isCompletionOverrideReasonAcceptable("          x")).toBe(false);
    expect(isCompletionOverrideReasonAcceptable("No attic access today")).toBe(true);
  });
});

describe("follow-up questions", () => {
  it("asks for the septic pump date only after Septic is chosen", () => {
    expect(visibleFieldsOfItem(sewer, {}).map((field) => field.key)).toEqual(["sewer_type"]);
    expect(visibleFieldsOfItem(sewer, { sewer_type: "city" }).map((field) => field.key)).toEqual(["sewer_type"]);
    expect(visibleFieldsOfItem(sewer, { sewer_type: "septic" }).map((field) => field.key)).toEqual(["sewer_type", "septic_last_pump_date"]);
  });

  it("asks for the well pump and filtration condition only after Well is chosen", () => {
    expect(visibleFieldsOfItem(waterSupply, { water_supply_type: "city" }).map((field) => field.key)).toEqual(["water_supply_type"]);
    expect(visibleFieldsOfItem(waterSupply, { water_supply_type: "well" }).map((field) => field.key)).toEqual([
      "water_supply_type",
      "well_pump_and_filtration_condition",
    ]);
  });

  it("hides the follow-up again when the answer switches back", () => {
    const fieldValues = { sewer_type: "city", septic_last_pump_date: "2024-03-01" };
    expect(visibleFieldsOfItem(sewer, fieldValues).map((field) => field.key)).toEqual(["sewer_type"]);
  });
});

describe("revealing one question at a time", () => {
  it("shows only the condition until a status is chosen", () => {
    expect(revealedQuestionCount(sewer, undefined)).toBe(1);
    expect(revealedQuestionCount(sewer, answered("not_checked", { sewer_type: "septic" }))).toBe(1);
  });

  it("reveals the next field after the status, then the follow-up, then photos and notes", () => {
    expect(revealedQuestionCount(sewer, answered("ok"))).toBe(2);
    expect(revealedQuestionCount(sewer, answered("ok", { sewer_type: "septic" }))).toBe(3);
    const allAnswered = answered("ok", { sewer_type: "septic", septic_last_pump_date: "unknown" });
    expect(cardQuestionsOfItem(sewer, allAnswered.item_field_values).map((question) => question.kind)).toEqual(["status", "field", "field", "photos_and_notes"]);
    expect(revealedQuestionCount(sewer, allAnswered)).toBe(4);
  });

  it("skips straight to photos and notes when City needs no follow-up", () => {
    expect(revealedQuestionCount(sewer, answered("ok", { sewer_type: "city" }))).toBe(3);
    expect(cardQuestionsOfItem(sewer, { sewer_type: "city" }).at(-1)).toEqual({ kind: "photos_and_notes" });
  });
});

describe("the window replacement counter", () => {
  it("stays between the configured bounds and only holds whole numbers", () => {
    expect(clampCounterValue(windowsCounterField, -1)).toBe(0);
    expect(clampCounterValue(windowsCounterField, 3)).toBe(3);
    expect(clampCounterValue(windowsCounterField, 100)).toBe(99);
    expect(clampCounterValue(windowsCounterField, 2.6)).toBe(3);
    expect(clampCounterValue(windowsCounterField, Number.NaN)).toBe(0);
  });
});

describe("progress", () => {
  it("counts checked items per level and overall", () => {
    const answers = { roof: answered("ok"), windows: answered("replace"), hvac: answered("not_checked") };
    const structure = levelProgress(INSPECTION_CHECKLIST_CONFIG.sections[0]!, answers);
    expect(structure).toEqual({ sectionKey: "structure_and_exterior", checkedItemCount: 2, totalItemCount: 4, isComplete: false });
    expect(overallProgressFraction(answers)).toBeCloseTo(0.2);
  });

  it("marks a level complete when all its items are checked", () => {
    const answers = { roof: answered("ok"), foundation: answered("ok"), walls_and_siding: answered("repair"), windows: answered("ok") };
    expect(levelProgress(INSPECTION_CHECKLIST_CONFIG.sections[0]!, answers).isComplete).toBe(true);
  });

  it("moves to the next and previous card in config order, across levels", () => {
    expect(neighbourItemKey("windows", 1)).toBe("hvac");
    expect(neighbourItemKey("hvac", -1)).toBe("windows");
    expect(neighbourItemKey("roof", -1)).toBeUndefined();
    expect(neighbourItemKey("water_supply", 1)).toBeUndefined();
  });
});

describe("formatting and sharing", () => {
  it("formats choices, unknowns and the age of a year", () => {
    expect(formatFieldValue(sewer.fields[0]!, "septic")).toBe("Septic");
    expect(formatFieldValue(sewer.fields[1]!, "unknown")).toBe("Unknown");
    expect(formatFieldValue(sewer.fields[1]!, undefined)).toBe("—");
    expect(approximateAgeLabel(2014, 2026)).toBe("≈ 12 years old");
    expect(approximateAgeLabel("unknown", 2026)).toBe("");
  });

  it("lists Replace, then Repair, then the windows and OK items, with fields and notes", () => {
    const text = inspectionShareText(
      { property_address: "12 Palm Ave", inspection_date: "2026-10-28", inspector_name: "Aviv", completion_override_reason: null },
      {
        roof: answered("replace", { roof_type: "shingle", roof_install_year: 2004 }, "Soft spots by the chimney"),
        windows: answered("repair", { windows_needing_replacement_count: 3 }),
        sewer: answered("ok", { sewer_type: "city", septic_last_pump_date: "2020-01-01" }),
      },
      "https://example.test/inspections/abc/summary",
    );
    expect(text).toContain("REPLACE:\n- Roof (Roof type: Shingle; Approximate install year: 2004; Notes: Soft spots by the chimney)");
    expect(text).toContain("REPAIR:\n- Windows (Windows that need replacement: 3)");
    expect(text.indexOf("REPLACE")).toBeLessThan(text.indexOf("REPAIR"));
    expect(text).toContain("Windows to replace: 3");
    expect(text).toContain("OK: Sewer");
    expect(text).not.toContain("2020"); // the septic date no longer applies to a city sewer
    expect(text.endsWith("https://example.test/inspections/abc/summary")).toBe(true);
  });
});
