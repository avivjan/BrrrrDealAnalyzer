import type { InspectionItemStatus } from "./inspectionChecklistLogic";

/** How each item status looks: a semantic token always paired with an icon (design-system pages/inspection.md). */
export interface InspectionStatusAppearance {
  label: string;
  icon: string;
  textClass: string;
  selectedClass: string;
  chipClass: string;
}

export const INSPECTION_STATUS_APPEARANCE: Record<InspectionItemStatus, InspectionStatusAppearance> = {
  not_checked: {
    label: "Not checked",
    icon: "pi pi-circle",
    textClass: "text-fg-muted",
    selectedClass: "border-line bg-surface-2 text-fg",
    chipClass: "border-line bg-surface text-fg-muted",
  },
  ok: {
    label: "OK",
    icon: "pi pi-check",
    textClass: "text-positive",
    selectedClass: "border-positive bg-positive/15 text-positive shadow-2",
    chipClass: "border-positive/50 bg-positive/10 text-positive",
  },
  repair: {
    label: "Repair",
    icon: "pi pi-wrench",
    textClass: "text-warning",
    selectedClass: "border-warning bg-warning/15 text-warning shadow-2",
    chipClass: "border-warning/50 bg-warning/10 text-warning",
  },
  replace: {
    label: "Replace",
    icon: "pi pi-refresh",
    textClass: "text-negative",
    selectedClass: "border-negative bg-negative/15 text-negative shadow-2",
    chipClass: "border-negative/50 bg-negative/10 text-negative",
  },
};

export const CHOOSABLE_ITEM_STATUSES: InspectionItemStatus[] = ["ok", "repair", "replace"];
