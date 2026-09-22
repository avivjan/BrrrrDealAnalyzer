/**
 * The calculation breakdown as a tree, answer first.
 *
 * The backend files a section's steps in calculation order, so the headline
 * is last and its components are scattered above it. These helpers turn one
 * section into rows that read the other way round: the headline's operands
 * are the first rows, and any operand that is itself a computed step (the
 * backend stamps it with `step_label`) can be expanded into its own operands,
 * down to the raw inputs. Nothing here computes a number.
 *
 * A row's `path` is its position in the tree ("2/0/1"); the popup keeps the
 * set of expanded paths, so the same figure appearing twice (a step reached
 * from two parents) opens and closes independently.
 */
import type { CalcBreakdowns, CalcStep } from "../../types";

export interface CalculationBreakdownRow {
  path: string;
  /** "+" / "-" for an operand; null for a step listed as an input of a non-sum headline. */
  sign: "+" | "-" | null;
  label: string;
  value: number;
  unit: CalcStep["unit"];
  /** The step this row is the value of; present exactly when the row can be expanded. */
  linkedStep?: CalcStep;
}

/** The step that *is* the tile's number: the last one whose value equals it, else the last step. */
export function findHeadlineStepIndex(steps: CalcStep[], metricValue: number | undefined): number {
  if (steps.length === 0) return -1;
  if (metricValue !== undefined) {
    for (let index = steps.length - 1; index >= 0; index -= 1) {
      if (steps[index]!.value === metricValue) return index;
    }
  }
  return steps.length - 1;
}

/** The step carrying `label`: the section it was referenced from first, then every section in order. */
export function findStepByLabel(
  breakdowns: CalcBreakdowns,
  preferredSectionKey: string,
  label: string,
): CalcStep | undefined {
  const own = breakdowns[preferredSectionKey]?.find((step) => step.label === label);
  if (own) return own;
  for (const steps of Object.values(breakdowns)) {
    const found = steps.find((step) => step.label === label);
    if (found) return found;
  }
  return undefined;
}

export function isSumStep(step: CalcStep): boolean {
  return Boolean(step.terms && step.terms.length > 0);
}

/**
 * The rows under a step: one per operand of a sum step, linked to its source
 * step when the backend named one and that step is not already an ancestor
 * (a guard against a cycle that the engine never produces but that would
 * otherwise recurse forever). A non-sum step has no rows; its formula is shown.
 */
export function rowsOfStep(
  step: CalcStep,
  breakdowns: CalcBreakdowns,
  sectionKey: string,
  parentPath: string,
  ancestorStepLabels: ReadonlySet<string>,
): CalculationBreakdownRow[] {
  if (!isSumStep(step)) return [];
  return step.terms!.map((term, index) => {
    const linkedStep =
      term.step_label && !ancestorStepLabels.has(term.step_label)
        ? findStepByLabel(breakdowns, sectionKey, term.step_label)
        : undefined;
    return {
      path: parentPath ? `${parentPath}/${index}` : String(index),
      sign: term.sign,
      label: term.label,
      value: term.value,
      unit: linkedStep?.unit ?? "money",
      linkedStep,
    };
  });
}

/** Steps of the section listed as expandable rows (a non-sum headline's inputs, or the steps derived after it). */
export function rowsOfSteps(steps: CalcStep[], pathPrefix: string): CalculationBreakdownRow[] {
  return steps.map((step, index) => ({
    path: `${pathPrefix}/${index}`,
    sign: null,
    label: step.label,
    value: step.value,
    unit: step.unit,
    linkedStep: step,
  }));
}

/**
 * The first rows of the popup. A sum headline shows its operands; a non-sum
 * headline (DSCR, the returns, a mortgage-type figure) shows the section's
 * earlier steps, which are its inputs by construction.
 */
export function topLevelRowsForHeadline(
  breakdowns: CalcBreakdowns,
  sectionKey: string,
  headlineIndex: number,
): CalculationBreakdownRow[] {
  const steps = breakdowns[sectionKey] ?? [];
  const headline = steps[headlineIndex];
  if (!headline) return [];
  if (isSumStep(headline)) {
    return rowsOfStep(headline, breakdowns, sectionKey, "", new Set([headline.label]));
  }
  return rowsOfSteps(steps.slice(0, headlineIndex), "input");
}

export function stepsAfterHeadline(steps: CalcStep[], headlineIndex: number): CalcStep[] {
  return headlineIndex >= 0 ? steps.slice(headlineIndex + 1) : [];
}

export function isRowExpandable(row: CalculationBreakdownRow): boolean {
  return row.linkedStep !== undefined;
}

/** Every expandable path under `rows`, recursively, for "Expand all". */
export function allExpandableRowPaths(
  rows: CalculationBreakdownRow[],
  breakdowns: CalcBreakdowns,
  sectionKey: string,
  ancestorStepLabels: ReadonlySet<string>,
): string[] {
  const paths: string[] = [];
  for (const row of rows) {
    if (!row.linkedStep) continue;
    paths.push(row.path);
    const ancestors = new Set(ancestorStepLabels);
    ancestors.add(row.linkedStep.label);
    const children = rowsOfStep(row.linkedStep, breakdowns, sectionKey, row.path, ancestors);
    paths.push(...allExpandableRowPaths(children, breakdowns, sectionKey, ancestors));
  }
  return paths;
}

/** The paths open when the popup appears: every expandable row of the first level. */
export function defaultExpandedRowPaths(rows: CalculationBreakdownRow[]): string[] {
  return rows.filter(isRowExpandable).map((row) => row.path);
}
