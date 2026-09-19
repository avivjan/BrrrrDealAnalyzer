/**
 * Read/write helpers for a deal object the form mutates IN PLACE.
 *
 * Lifted out of `DealInputsForm.vue` so the four lifecycle sections share one set of
 * accessors. The rules they encode (see the form's header comment for the history):
 *
 * - **No default substituted on read or write.** Doing so made LTV and the long term
 *   rate impossible to retype. Defaults belong to `createEmptyDealForm` and the backend.
 * - **Clearing stores `undefined`, not `0`**, so the field is omitted from the payload.
 * - **`toNumber` on every read**, because a saved deal carries its money and percentage
 *   fields as strings (FastAPI serialises `Decimal` that way).
 * - **`setNullable` stores `null`** for the formula-defaulted fields, where `null` means
 *   "use the formula" and must reach the backend (an `undefined` would be dropped).
 */
import type { DealInputModel } from "../types";
import { toNumber } from "../utils/dealUtils";

/** Keys on `DealInputModel` whose value is a number (or a nullable number). */
export type NumericKey = {
  [K in keyof DealInputModel]-?: number extends NonNullable<DealInputModel[K]> ? K : never;
}[keyof DealInputModel];

export type BooleanKey = {
  [K in keyof DealInputModel]-?: boolean extends NonNullable<DealInputModel[K]> ? K : never;
}[keyof DealInputModel];

export type StringKey = {
  [K in keyof DealInputModel]-?: string extends NonNullable<DealInputModel[K]> ? K : never;
}[keyof DealInputModel];

export function useDealField(deal: DealInputModel) {
  const record = deal as Record<string, unknown>;

  function get(key: NumericKey): number | null {
    return toNumber(record[key]) ?? null;
  }
  function set(key: NumericKey, value: number | null): void {
    record[key] = value ?? undefined;
  }
  /** For "null = formula default" fields: `null` is a real value and is kept. */
  function setNullable(key: NumericKey, value: number | null): void {
    record[key] = value;
  }
  /** `null` when the field is unset (so a formula default applies), else the number. */
  function getNullable(key: NumericKey): number | null {
    return toNumber(record[key]) ?? null;
  }
  function getBool(key: BooleanKey, fallback: boolean): boolean {
    const v = record[key];
    return typeof v === "boolean" ? v : fallback;
  }
  function setBool(key: BooleanKey, value: boolean | null): void {
    record[key] = value;
  }
  function getStr(key: StringKey): string | null {
    const v = record[key];
    return typeof v === "string" && v !== "" ? v : null;
  }
  function setStr(key: StringKey, value: string | null): void {
    record[key] = value;
  }
  return { get, set, getNullable, setNullable, getBool, setBool, getStr, setStr };
}
