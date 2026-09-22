<script setup lang="ts">
/**
 * "How is this number calculated?" — the popup behind every result tile in
 * the deal modals.
 *
 * It opens on the answer: the headline step's operands as the first rows,
 * ending on the "= headline value" line, and any operand that is itself a
 * computed step (the backend names it in `step_label`) expands in place into
 * its own operands or its formula, down to the raw inputs. The first level is
 * open on arrival; "Expand all" / "Collapse all" do the rest. A headline that
 * is not a sum (DSCR, the returns) shows its formula first and the section's
 * earlier steps as its inputs beneath. Steps the section derives *after* the
 * headline (the cash to the refi table from the lowest-ARV wire) follow under
 * their own caption, and a collapsed "All steps" list keeps the calculation
 * order at hand.
 *
 * It computes nothing: the numbers are the engine's own, and every equation
 * in the text was verified against the engine before the response left the
 * server (`BackEnd/BL/analyze/explain/`).
 *
 * The overlay follows `UiDrawer`: teleported to `<body>` (so the `v-reveal`
 * transform on the tile grid cannot misplace a fixed box), `z-[60]` above the
 * deal modal's `z-50`, closes on the scrim, the close button and a
 * document-level Escape that it claims with `preventDefault` so nothing
 * underneath acts on the same key, focus moved into the panel while open and
 * restored to the pressed tile on close, and everything else on the page
 * `inert` meanwhile.
 */
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from "vue";

import type { CalcBreakdowns, CalcStep } from "../../types";
import { inertOutside } from "../ui/inertOutside";
import {
  allExpandableRowPaths,
  defaultExpandedRowPaths,
  findHeadlineStepIndex,
  isSumStep,
  rowsOfSteps,
  stepsAfterHeadline,
  topLevelRowsForHeadline,
} from "./calculationBreakdownTree";
import CalculationBreakdownTreeRow from "./CalculationBreakdownTreeRow.vue";
import { formatCalculationStepValueByUnit } from "./calculationStepFormat";

const props = withDefaults(
  defineProps<{
    open: boolean;
    /** The tile's caption, e.g. "Cash Flow"; names the dialog. */
    metricLabel: string;
    /** The result key, e.g. "cash_flow": the breakdown section to show. */
    metricKey: string;
    /** Every section of the current analysis; a term can point at a step filed under another section. */
    breakdowns?: CalcBreakdowns;
    /** The number on the tile (`analysis[metricKey]`); picks the headline step, since a section may end on a derived reading. */
    metricValue?: number;
  }>(),
  { breakdowns: undefined, metricValue: undefined },
);

const emit = defineEmits<{ close: [] }>();

const headingId = useId();
const overlayRoot = ref<HTMLElement | null>(null);

const steps = computed<CalcStep[]>(() => props.breakdowns?.[props.metricKey] ?? []);
const headlineStepIndex = computed(() => findHeadlineStepIndex(steps.value, props.metricValue));
const headlineStep = computed<CalcStep | null>(() =>
  headlineStepIndex.value >= 0 ? steps.value[headlineStepIndex.value]! : null,
);
const headlineIsSum = computed(() => (headlineStep.value ? isSumStep(headlineStep.value) : false));
const headlineValueText = computed(() =>
  headlineStep.value ? formatCalculationStepValueByUnit(headlineStep.value.unit, headlineStep.value.value) : "",
);

const emptyBreakdowns: CalcBreakdowns = {};
const breakdownsOrEmpty = computed(() => props.breakdowns ?? emptyBreakdowns);
const rootAncestorStepLabels = computed<ReadonlySet<string>>(
  () => new Set(headlineStep.value ? [headlineStep.value.label] : []),
);
const topLevelRows = computed(() =>
  topLevelRowsForHeadline(breakdownsOrEmpty.value, props.metricKey, headlineStepIndex.value),
);
const derivedRows = computed(() => rowsOfSteps(stepsAfterHeadline(steps.value, headlineStepIndex.value), "derived"));

function formatStepValue(step: CalcStep): string {
  return formatCalculationStepValueByUnit(step.unit, step.value);
}

// -- expansion -------------------------------------------------------------
// Replaced, never mutated, so every row re-reads it.
const expandedRowPaths = ref<ReadonlySet<string>>(new Set());

function resetExpansionToTheFirstLevel() {
  expandedRowPaths.value = new Set([
    ...defaultExpandedRowPaths(topLevelRows.value),
    ...defaultExpandedRowPaths(derivedRows.value),
  ]);
}

function expandAllRows() {
  expandedRowPaths.value = new Set([
    ...allExpandableRowPaths(topLevelRows.value, breakdownsOrEmpty.value, props.metricKey, rootAncestorStepLabels.value),
    ...allExpandableRowPaths(derivedRows.value, breakdownsOrEmpty.value, props.metricKey, new Set()),
  ]);
}

function collapseAllRows() {
  expandedRowPaths.value = new Set();
}

function toggleRow(path: string) {
  const next = new Set(expandedRowPaths.value);
  if (next.has(path)) next.delete(path);
  else next.add(path);
  expandedRowPaths.value = next;
}

watch(
  () => [props.open, props.metricKey] as const,
  ([open]) => {
    if (open) resetExpansionToTheFirstLevel();
  },
  { immediate: true },
);

// -- overlay behaviour -------------------------------------------------------
/**
 * Escape closes the popup from anywhere on the page while it is open. A
 * `document` listener rather than `@keydown` on the root, for the reasons
 * `UiDrawer` gives; and the key is claimed with `preventDefault` so a handler
 * on the deal modal underneath never sees an Escape meant for this popup.
 */
function onDocumentKeydown(event: KeyboardEvent) {
  if (event.key !== "Escape" || event.defaultPrevented) return;
  event.preventDefault();
  emit("close");
}

function listen(open: boolean) {
  if (typeof document === "undefined") return;
  document.removeEventListener("keydown", onDocumentKeydown);
  if (open) document.addEventListener("keydown", onDocumentKeydown);
}

let restoreFocusTo: HTMLElement | null = null;
let releaseInert: (() => void) | null = null;

onBeforeUnmount(() => {
  listen(false);
  releaseInert?.();
  releaseInert = null;
});

watch(
  () => props.open,
  async (open) => {
    if (typeof document === "undefined") return;
    listen(open);
    if (open) {
      restoreFocusTo = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      await nextTick();
      const panel = overlayRoot.value?.querySelector<HTMLElement>('[data-ui="modal-panel"]') ?? null;
      panel?.focus();
      releaseInert?.();
      releaseInert = overlayRoot.value ? inertOutside(overlayRoot.value) : null;
    } else {
      releaseInert?.();
      releaseInert = null;
      if (restoreFocusTo) {
        restoreFocusTo.focus();
        restoreFocusTo = null;
      }
    }
  },
  { immediate: true },
);
</script>

<template>
  <Teleport to="body">
    <UiTransition preset="modalEnterOnly">
      <div
        v-if="open"
        ref="overlayRoot"
        data-overlay
        data-testid="calculation-breakdown-popup"
        :data-metric-key="metricKey"
        class="fixed inset-0 z-[60] flex items-center justify-center bg-fg/60 p-4 md:backdrop-blur-sm"
        @click.self="emit('close')"
      >
        <UiModalPanel size="lg" :labelled-by="headingId" tabindex="-1" class="outline-none">
          <template #header>
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <h2 :id="headingId" class="text-base font-semibold text-fg">
                  How {{ metricLabel }} is calculated
                </h2>
                <p
                  v-if="headlineStep"
                  data-part="headline-value"
                  class="numeric font-display text-xl font-bold tracking-display text-fg"
                >
                  {{ headlineValueText }}
                </p>
              </div>
              <div class="flex shrink-0 items-center gap-1">
                <UiButton v-if="headlineStep" data-part="expand-all" variant="ghost" size="sm" @click="expandAllRows">
                  Expand all
                </UiButton>
                <UiButton v-if="headlineStep" data-part="collapse-all" variant="ghost" size="sm" @click="collapseAllRows">
                  Collapse all
                </UiButton>
                <UiIconButton label="Close" data-part="close" @click="emit('close')">
                  <i class="pi pi-times" aria-hidden="true"></i>
                </UiIconButton>
              </div>
            </div>
          </template>

          <template v-if="headlineStep">
            <!-- A headline that is not a sum: its formula first, then the section's steps as its inputs. -->
            <div
              v-if="!headlineIsSum"
              data-part="headline-formula"
              class="mb-3 rounded-card border border-primary/40 bg-primary/5 p-3"
            >
              <p class="break-words font-mono text-xs leading-relaxed text-fg">{{ headlineStep.formula }}</p>
              <p v-if="headlineStep.note" data-part="headline-note" class="mt-2 text-xs text-fg-muted">
                {{ headlineStep.note }}
              </p>
              <p v-if="topLevelRows.length" class="mt-2 text-xs font-semibold uppercase tracking-wider text-fg-muted">
                Built from
              </p>
            </div>

            <ul
              v-if="topLevelRows.length || headlineIsSum"
              data-part="tree"
              class="m-0 list-none rounded-card border border-line bg-surface-2 px-3 py-1"
            >
              <CalculationBreakdownTreeRow
                v-for="row in topLevelRows"
                :key="row.path"
                :row="row"
                :depth="0"
                :ancestor-step-labels="rootAncestorStepLabels"
                :expanded-row-paths="expandedRowPaths"
                :breakdowns="breakdownsOrEmpty"
                :section-key="metricKey"
                @toggle="toggleRow"
              />
              <li
                v-if="headlineIsSum"
                data-part="headline-total"
                class="grid grid-cols-[1.25rem_1rem_minmax(0,1fr)_auto] items-baseline gap-x-2 border-t-2 border-primary/40 py-2 text-sm font-bold"
              >
                <span aria-hidden="true"></span>
                <span class="text-center font-mono text-fg-muted">=</span>
                <span class="truncate text-fg">{{ headlineStep.label }}</span>
                <span class="numeric tabular text-fg">{{ headlineValueText }}</span>
              </li>
            </ul>
            <p v-if="headlineIsSum && headlineStep.note" data-part="headline-note" class="mt-2 text-xs text-fg-muted">
              {{ headlineStep.note }}
            </p>

            <template v-if="derivedRows.length">
              <p data-part="derived-caption" class="mb-1 mt-4 text-xs font-semibold uppercase tracking-wider text-fg-muted">
                Derived from this
              </p>
              <ul data-part="derived-tree" class="m-0 list-none rounded-card border border-line bg-surface-2 px-3 py-1">
                <CalculationBreakdownTreeRow
                  v-for="row in derivedRows"
                  :key="row.path"
                  :row="row"
                  :depth="0"
                  :ancestor-step-labels="new Set<string>()"
                  :expanded-row-paths="expandedRowPaths"
                  :breakdowns="breakdownsOrEmpty"
                  :section-key="metricKey"
                  @toggle="toggleRow"
                />
              </ul>
            </template>

            <details data-part="all-steps" class="mt-4">
              <summary class="cursor-pointer text-xs font-semibold uppercase tracking-wider text-fg-muted">
                All {{ steps.length }} steps in calculation order
              </summary>
              <ol class="mt-2 space-y-2">
                <li
                  v-for="(step, stepIndex) in steps"
                  :key="stepIndex"
                  data-part="all-steps-item"
                  class="rounded-card border border-line bg-surface-2 p-3"
                >
                  <div class="flex items-baseline justify-between gap-3">
                    <span class="text-sm font-semibold text-fg">{{ step.label }}</span>
                    <span class="numeric tabular text-sm font-bold text-fg">{{ formatStepValue(step) }}</span>
                  </div>
                  <p class="mt-1 break-words font-mono text-xs leading-relaxed text-fg">{{ step.formula }}</p>
                  <p v-if="step.note" class="mt-1 text-xs text-fg-muted">{{ step.note }}</p>
                </li>
              </ol>
            </details>
          </template>
          <p v-else data-part="empty" class="text-sm text-fg-muted">
            No breakdown available for this result. Re-open the deal to fetch a fresh analysis.
          </p>

          <template #footer>
            <p class="text-xs text-fg-muted">
              Money is in dollars, percentages as shown, ratios as a multiple (1.20x).
              "∞" and "-∞" mean the divisor was zero. A note under a step explains a convention.
            </p>
          </template>
        </UiModalPanel>
      </div>
    </UiTransition>
  </Teleport>
</template>
