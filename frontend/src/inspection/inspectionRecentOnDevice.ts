/**
 * "Recent on this device": how an anonymous inspector finds their inspections
 * again, since there is deliberately no public list of inspections. Only the
 * id, address and date are kept, in localStorage `bw.inspections.recentOnDevice`.
 */
export interface RecentInspectionOnDevice {
  inspection_id: string;
  property_address: string;
  inspection_date: string;
  last_opened_at: string;
}

export const RECENT_INSPECTIONS_STORAGE_KEY = "bw.inspections.recentOnDevice";
export const MAXIMUM_RECENT_INSPECTIONS_ON_DEVICE = 20;

export function readRecentInspectionsOnDevice(): RecentInspectionOnDevice[] {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(RECENT_INSPECTIONS_STORAGE_KEY) || "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (entry): entry is RecentInspectionOnDevice =>
        entry && typeof entry.inspection_id === "string" && typeof entry.property_address === "string" && typeof entry.inspection_date === "string",
    );
  } catch {
    return [];
  }
}

function writeRecentInspectionsOnDevice(entries: RecentInspectionOnDevice[]): void {
  try {
    window.localStorage.setItem(RECENT_INSPECTIONS_STORAGE_KEY, JSON.stringify(entries));
  } catch {
    /* private mode or full storage: the list just isn't remembered */
  }
}

/** Moves the inspection to the top of the list, newest first, at most 20. */
export function rememberInspectionOnDevice(entry: Omit<RecentInspectionOnDevice, "last_opened_at">, now: Date = new Date()): RecentInspectionOnDevice[] {
  const others = readRecentInspectionsOnDevice().filter((existing) => existing.inspection_id !== entry.inspection_id);
  const updated = [{ ...entry, last_opened_at: now.toISOString() }, ...others].slice(0, MAXIMUM_RECENT_INSPECTIONS_ON_DEVICE);
  writeRecentInspectionsOnDevice(updated);
  return updated;
}

export function forgetInspectionOnDevice(inspectionId: string): RecentInspectionOnDevice[] {
  const remaining = readRecentInspectionsOnDevice().filter((existing) => existing.inspection_id !== inspectionId);
  writeRecentInspectionsOnDevice(remaining);
  return remaining;
}
