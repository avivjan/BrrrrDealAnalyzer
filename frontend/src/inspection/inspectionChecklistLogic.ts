/**
 * The property inspection checklist, as data plus pure rules.
 *
 * `inspectionChecklistConfig.json` is a byte-identical copy of the backend's
 * `BL/inspection/inspection_checklist_config.json` (a backend test keeps them
 * equal). Everything the walkthrough shows comes from it: levels (sections),
 * cards (items), the questions on each card, and the follow-ups that appear
 * only when relevant. Nothing here touches the network or the DOM, so every
 * rule is unit-tested on its own (`inspectionChecklistLogic.test.ts`).
 */
import inspectionChecklistConfigJson from "./inspectionChecklistConfig.json";

export type InspectionItemStatus = "not_checked" | "ok" | "repair" | "replace";

export type InspectionFieldType = "choice" | "year_or_unknown" | "text_or_unknown" | "date_or_unknown" | "counter" | "text";

export interface InspectionFieldOption {
  value: string;
  label: string;
}

export interface InspectionFieldConfig {
  key: string;
  label: string;
  type: InspectionFieldType;
  options?: InspectionFieldOption[];
  minimum_count?: number;
  maximum_count?: number;
  show_when?: { field_key: string; equals: string };
}

export interface InspectionItemConfig {
  key: string;
  label: string;
  description: string;
  is_critical: boolean;
  photo_prompt?: string;
  fields: InspectionFieldConfig[];
}

export interface InspectionSectionConfig {
  key: string;
  label: string;
  items: InspectionItemConfig[];
}

export interface InspectionChecklistConfig {
  checklist_config_version: number;
  item_statuses: { value: InspectionItemStatus; label: string }[];
  sections: InspectionSectionConfig[];
}

export type InspectionFieldValue = string | number;
export type InspectionFieldValues = Record<string, InspectionFieldValue>;

/** What the walkthrough knows about one item: a missing entry means "not checked". */
export interface InspectionItemAnswers {
  item_status: InspectionItemStatus;
  item_notes: string | null;
  item_field_values: InspectionFieldValues;
}

export const INSPECTION_CHECKLIST_CONFIG = inspectionChecklistConfigJson as InspectionChecklistConfig;
export const UNKNOWN_FIELD_VALUE = "unknown";
export const MINIMUM_COMPLETION_OVERRIDE_REASON_LENGTH = 10;
export const WINDOWS_ITEM_KEY = "windows";
export const WINDOWS_NEEDING_REPLACEMENT_FIELD_KEY = "windows_needing_replacement_count";

export const ITEM_STATUS_LABELS: Record<InspectionItemStatus, string> = {
  not_checked: "Not checked",
  ok: "OK",
  repair: "Repair",
  replace: "Replace",
};

export function allChecklistItems(config: InspectionChecklistConfig = INSPECTION_CHECKLIST_CONFIG): InspectionItemConfig[] {
  return config.sections.flatMap((section) => section.items);
}

export function findChecklistItem(itemKey: string, config: InspectionChecklistConfig = INSPECTION_CHECKLIST_CONFIG): InspectionItemConfig | undefined {
  return allChecklistItems(config).find((item) => item.key === itemKey);
}

export function sectionOfItem(itemKey: string, config: InspectionChecklistConfig = INSPECTION_CHECKLIST_CONFIG): InspectionSectionConfig | undefined {
  return config.sections.find((section) => section.items.some((item) => item.key === itemKey));
}

export function itemStatusOf(itemKey: string, answersByItemKey: Record<string, InspectionItemAnswers>): InspectionItemStatus {
  return answersByItemKey[itemKey]?.item_status ?? "not_checked";
}

export function isItemChecked(itemKey: string, answersByItemKey: Record<string, InspectionItemAnswers>): boolean {
  return itemStatusOf(itemKey, answersByItemKey) !== "not_checked";
}

/** A follow-up applies only while its condition holds (Septic → last pump date). */
export function isFieldVisible(field: InspectionFieldConfig, fieldValues: InspectionFieldValues): boolean {
  if (!field.show_when) return true;
  return fieldValues[field.show_when.field_key] === field.show_when.equals;
}

export function visibleFieldsOfItem(item: InspectionItemConfig, fieldValues: InspectionFieldValues): InspectionFieldConfig[] {
  return item.fields.filter((field) => isFieldVisible(field, fieldValues));
}

export function isFieldAnswered(field: InspectionFieldConfig, fieldValues: InspectionFieldValues): boolean {
  const value = fieldValues[field.key];
  return value !== undefined && value !== null && value !== "";
}

/**
 * The questions of a card, revealed one at a time: status first, then each
 * visible field, then the optional photo/notes step. Returns how many of
 * them should be on screen: every answered question plus the next one.
 */
export type InspectionCardQuestion = { kind: "status" } | { kind: "field"; field: InspectionFieldConfig } | { kind: "photos_and_notes" };

export function cardQuestionsOfItem(item: InspectionItemConfig, fieldValues: InspectionFieldValues): InspectionCardQuestion[] {
  return [
    { kind: "status" },
    ...visibleFieldsOfItem(item, fieldValues).map((field) => ({ kind: "field" as const, field })),
    { kind: "photos_and_notes" },
  ];
}

export function revealedQuestionCount(item: InspectionItemConfig, answers: InspectionItemAnswers | undefined): number {
  const questions = cardQuestionsOfItem(item, answers?.item_field_values ?? {});
  if (!answers || answers.item_status === "not_checked") return 1;
  let revealed = 1;
  for (const question of questions.slice(1)) {
    revealed += 1;
    if (question.kind === "field" && !isFieldAnswered(question.field, answers.item_field_values)) break;
  }
  return revealed;
}

export interface LevelProgress {
  sectionKey: string;
  checkedItemCount: number;
  totalItemCount: number;
  isComplete: boolean;
}

export function levelProgress(section: InspectionSectionConfig, answersByItemKey: Record<string, InspectionItemAnswers>): LevelProgress {
  const checkedItemCount = section.items.filter((item) => isItemChecked(item.key, answersByItemKey)).length;
  return {
    sectionKey: section.key,
    checkedItemCount,
    totalItemCount: section.items.length,
    isComplete: checkedItemCount === section.items.length,
  };
}

export function overallProgressFraction(answersByItemKey: Record<string, InspectionItemAnswers>, config: InspectionChecklistConfig = INSPECTION_CHECKLIST_CONFIG): number {
  const items = allChecklistItems(config);
  if (items.length === 0) return 0;
  return items.filter((item) => isItemChecked(item.key, answersByItemKey)).length / items.length;
}

/** The "missions left": CRITICAL items that are still not checked. */
export function remainingCriticalItems(answersByItemKey: Record<string, InspectionItemAnswers>, config: InspectionChecklistConfig = INSPECTION_CHECKLIST_CONFIG): InspectionItemConfig[] {
  return allChecklistItems(config).filter((item) => item.is_critical && !isItemChecked(item.key, answersByItemKey));
}

export type FinishEligibility =
  | { canFinish: true; needsOverrideReason: false }
  | { canFinish: false; needsOverrideReason: true; remainingCriticalItemLabels: string[] };

/** "Finish" is blocked until every CRITICAL item has a status; an explicit override with a reason is the only way past. */
export function finishEligibility(answersByItemKey: Record<string, InspectionItemAnswers>, config: InspectionChecklistConfig = INSPECTION_CHECKLIST_CONFIG): FinishEligibility {
  const remaining = remainingCriticalItems(answersByItemKey, config);
  if (remaining.length === 0) return { canFinish: true, needsOverrideReason: false };
  return { canFinish: false, needsOverrideReason: true, remainingCriticalItemLabels: remaining.map((item) => item.label) };
}

export function isCompletionOverrideReasonAcceptable(reason: string): boolean {
  return reason.trim().length >= MINIMUM_COMPLETION_OVERRIDE_REASON_LENGTH;
}

export function clampCounterValue(field: InspectionFieldConfig, value: number): number {
  const minimum = field.minimum_count ?? 0;
  const maximum = field.maximum_count ?? 99;
  if (!Number.isFinite(value)) return minimum;
  return Math.min(maximum, Math.max(minimum, Math.round(value)));
}

/** The next and previous card, in config order, for swipes and the ◀ ▶ buttons. */
export function neighbourItemKey(itemKey: string, direction: 1 | -1, config: InspectionChecklistConfig = INSPECTION_CHECKLIST_CONFIG): string | undefined {
  const keys = allChecklistItems(config).map((item) => item.key);
  const index = keys.indexOf(itemKey);
  if (index === -1) return undefined;
  return keys[index + direction];
}

export function formatFieldValue(field: InspectionFieldConfig, value: InspectionFieldValue | undefined): string {
  if (value === undefined || value === null || value === "") return "—";
  if (value === UNKNOWN_FIELD_VALUE) return "Unknown";
  if (field.type === "choice") return field.options?.find((option) => option.value === value)?.label ?? String(value);
  if (field.type === "date_or_unknown" && typeof value === "string") {
    const [year, month, day] = value.split("-").map(Number);
    if (year && month && day) return new Date(year, month - 1, day).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
  }
  return String(value);
}

/** "≈ 12 years old" next to a year answer, so age and install year are both covered. */
export function approximateAgeLabel(year: InspectionFieldValue | undefined, currentYear: number = new Date().getFullYear()): string {
  if (typeof year !== "number") return "";
  const ageInYears = currentYear - year;
  if (ageInYears <= 0) return "brand new";
  return ageInYears === 1 ? "≈ 1 year old" : `≈ ${ageInYears} years old`;
}

export interface ShareableInspection {
  property_address: string;
  inspection_date: string;
  inspector_name: string | null;
  completion_override_reason: string | null;
}

/** The plain-text summary the Share button sends to a contractor or partner. */
export function inspectionShareText(
  inspection: ShareableInspection,
  answersByItemKey: Record<string, InspectionItemAnswers>,
  inspectionLink: string,
  config: InspectionChecklistConfig = INSPECTION_CHECKLIST_CONFIG,
): string {
  const lines: string[] = [`Inspection: ${inspection.property_address}`, `Date: ${inspection.inspection_date}`];
  if (inspection.inspector_name) lines.push(`Inspector: ${inspection.inspector_name}`);
  const describe = (item: InspectionItemConfig) => {
    const answers = answersByItemKey[item.key];
    const fieldValues = answers?.item_field_values ?? {};
    const details = visibleFieldsOfItem(item, fieldValues)
      .filter((field) => isFieldAnswered(field, fieldValues))
      .map((field) => `${field.label}: ${formatFieldValue(field, fieldValues[field.key])}`);
    if (answers?.item_notes) details.push(`Notes: ${answers.item_notes}`);
    return details.length ? `- ${item.label} (${details.join("; ")})` : `- ${item.label}`;
  };
  for (const status of ["replace", "repair"] as const) {
    const items = allChecklistItems(config).filter((item) => itemStatusOf(item.key, answersByItemKey) === status);
    if (items.length) lines.push("", `${ITEM_STATUS_LABELS[status].toUpperCase()}:`, ...items.map(describe));
  }
  const windowsToReplace = Number(answersByItemKey[WINDOWS_ITEM_KEY]?.item_field_values?.[WINDOWS_NEEDING_REPLACEMENT_FIELD_KEY] ?? 0);
  lines.push("", `Windows to replace: ${windowsToReplace}`);
  const okItems = allChecklistItems(config).filter((item) => itemStatusOf(item.key, answersByItemKey) === "ok");
  if (okItems.length) lines.push(`OK: ${okItems.map((item) => item.label).join(", ")}`);
  const notChecked = allChecklistItems(config).filter((item) => !isItemChecked(item.key, answersByItemKey));
  if (notChecked.length) lines.push(`Not checked: ${notChecked.map((item) => item.label).join(", ")}`);
  if (inspection.completion_override_reason) lines.push(`Finished early because: ${inspection.completion_override_reason}`);
  lines.push("", inspectionLink);
  return lines.join("\n");
}
