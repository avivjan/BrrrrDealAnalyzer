/**
 * Item changes that have not reached the server yet, kept on this device.
 *
 * Houses often have poor signal, so every edit first lands here (per item,
 * merged), then the store sends it. A change stays until the server accepts
 * it, so a dropped connection, a closed tab or a reload never loses an answer.
 * Stored in localStorage under `bw.inspection.pendingChanges.<inspection id>`;
 * every read and write is wrapped so private mode or a full quota only means
 * "not persisted", never an error.
 */
import type { InspectionItemUpdateReq } from "../types/inspection";

export type PendingItemChangesByItemKey = Record<string, InspectionItemUpdateReq>;

export const PENDING_CHANGES_STORAGE_KEY_PREFIX = "bw.inspection.pendingChanges.";

/** Two edits of the same item become one request: later values win, field values merge key by key. */
export function mergePendingItemChange(existingChange: InspectionItemUpdateReq | undefined, nextChange: InspectionItemUpdateReq): InspectionItemUpdateReq {
  const merged: InspectionItemUpdateReq = { ...(existingChange ?? {}), ...nextChange };
  if (existingChange?.item_field_values || nextChange.item_field_values) {
    merged.item_field_values = { ...(existingChange?.item_field_values ?? {}), ...(nextChange.item_field_values ?? {}) };
  }
  return merged;
}

/**
 * After a request for `sentChange` succeeded, what is still pending: edits made
 * while it was in flight are kept, the parts the server now has are dropped.
 */
export function pendingChangeAfterSent(currentChange: InspectionItemUpdateReq | undefined, sentChange: InspectionItemUpdateReq): InspectionItemUpdateReq | undefined {
  if (!currentChange) return undefined;
  const remaining: InspectionItemUpdateReq = {};
  if (currentChange.item_status !== undefined && currentChange.item_status !== sentChange.item_status) remaining.item_status = currentChange.item_status;
  if (currentChange.item_notes !== undefined && currentChange.item_notes !== sentChange.item_notes) remaining.item_notes = currentChange.item_notes;
  const remainingFieldValues: Record<string, string | number | null> = {};
  for (const [fieldKey, value] of Object.entries(currentChange.item_field_values ?? {})) {
    if (sentChange.item_field_values?.[fieldKey] !== value) remainingFieldValues[fieldKey] = value;
  }
  if (Object.keys(remainingFieldValues).length) remaining.item_field_values = remainingFieldValues;
  return Object.keys(remaining).length ? remaining : undefined;
}

export function readPendingItemChanges(inspectionId: string): PendingItemChangesByItemKey {
  try {
    const stored = window.localStorage.getItem(PENDING_CHANGES_STORAGE_KEY_PREFIX + inspectionId);
    if (!stored) return {};
    const parsed = JSON.parse(stored);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as PendingItemChangesByItemKey) : {};
  } catch {
    return {};
  }
}

export function writePendingItemChanges(inspectionId: string, pendingChanges: PendingItemChangesByItemKey): void {
  try {
    if (Object.keys(pendingChanges).length === 0) window.localStorage.removeItem(PENDING_CHANGES_STORAGE_KEY_PREFIX + inspectionId);
    else window.localStorage.setItem(PENDING_CHANGES_STORAGE_KEY_PREFIX + inspectionId, JSON.stringify(pendingChanges));
  } catch {
    /* not persisted: the change still lives in memory and is retried */
  }
}
