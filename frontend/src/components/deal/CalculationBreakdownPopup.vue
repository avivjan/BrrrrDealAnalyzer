<script setup lang="ts">
/**
 * "How is this number calculated?" — the popup behind every result tile in
 * the deal modals.
 *
 * It renders one section of the backend's `breakdowns` (the ordered
 * `CalcStep[]` the explain layer emits for a headline metric): every step's
 * label, the formula with the concrete numbers substituted, the value read by
 * its unit, the stacked operands of a sum-type step and the optional note. The
 * last step is the headline, so it is also shown in the header.
 *
 * It computes nothing: the numbers are the engine's own, and every equation in
 * the text was verified against the engine before the response left the server
 * (`BackEnd/BL/analyze/explain/`).
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

import type { CalcStep } from "../../types";
import { inertOutside } from "../ui/inertOutside";
import {
  formatCalculationStepMoney,
  formatCalculationStepValueByUnit,
} from "./calculationStepFormat";

const props = withDefaults(
  defineProps<{
    open: boolean;
    /** The tile's caption, e.g. "Cash Flow"; names the dialog. */
    metricLabel: string;
    /** The result key, e.g. "cash_flow"; only used for test ids. */
    metricKey: string;
    /** `breakdowns[metricKey]` of the current analysis; empty when the response carried none. */
    steps?: CalcStep[];
    /** The number on the tile (`analysis[metricKey]`); picks the headline step, since a section may end on a derived reading. */
    metricValue?: number;
  }>(),
  { steps: undefined, metricValue: undefined },
);

const emit = defineEmits<{ close: [] }>();

const headingId = useId();
const overlayRoot = ref<HTMLElement | null>(null);

/**
 * The step that *is* the tile's number: the last one whose value equals it, or
 * the last step when no value was given. A section usually ends on its
 * headline, but not always: the lowest-ARV wire section ends on "Cash to Refi
 * Table", a reading derived from the wire.
 */
const headlineStepIndex = computed<number>(() => {
  const steps = props.steps ?? [];
  if (steps.length === 0) return -1;
  if (props.metricValue !== undefined) {
    for (let index = steps.length - 1; index >= 0; index -= 1) {
      if (steps[index]!.value === props.metricValue) return index;
    }
  }
  return steps.length - 1;
});

const headlineStep = computed<CalcStep | null>(() =>
  headlineStepIndex.value >= 0 ? props.steps![headlineStepIndex.value]! : null,
);

function formatStepValue(step: CalcStep): string {
  return formatCalculationStepValueByUnit(step.unit, step.value);
}

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
        <UiModalPanel size="md" :labelled-by="headingId" tabindex="-1" class="outline-none">
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
                  {{ formatStepValue(headlineStep) }}
                </p>
              </div>
              <UiIconButton label="Close" data-part="close" @click="emit('close')">
                <i class="pi pi-times" aria-hidden="true"></i>
              </UiIconButton>
            </div>
          </template>

          <ol v-if="steps && steps.length" data-part="steps" class="space-y-3">
            <li
              v-for="(step, stepIndex) in steps"
              :key="stepIndex"
              :data-part="stepIndex === headlineStepIndex ? 'headline-step' : 'step'"
              class="rounded-card border p-3"
              :class="
                stepIndex === headlineStepIndex
                  ? 'border-primary/40 bg-primary/5'
                  : 'border-line bg-surface-2'
              "
            >
              <div class="flex items-baseline justify-between gap-3">
                <span data-part="step-label" class="text-sm font-semibold text-fg">{{ step.label }}</span>
                <span data-part="step-value" class="numeric tabular text-sm font-bold text-fg">
                  {{ formatStepValue(step) }}
                </span>
              </div>

              <!-- A sum-type step stacks its operands; every other step shows its formula text. -->
              <ul
                v-if="step.terms && step.terms.length"
                data-part="step-terms"
                class="mt-2 space-y-0.5 text-sm"
              >
                <li
                  v-for="(term, termIndex) in step.terms"
                  :key="termIndex"
                  data-part="step-term"
                  class="flex justify-between gap-3"
                >
                  <span class="text-fg-muted">
                    <span data-part="term-sign" class="mr-1 inline-block w-3 text-center font-mono">{{ term.sign }}</span><span data-part="term-label">{{ term.label }}</span>
                  </span>
                  <span data-part="term-value" class="numeric tabular text-fg">{{ formatCalculationStepMoney(term.value) }}</span>
                </li>
                <li class="flex justify-between gap-3 border-t border-line pt-1 font-semibold">
                  <span class="text-fg-muted"><span class="mr-1 inline-block w-3 text-center font-mono">=</span>{{ step.label }}</span>
                  <span class="numeric tabular text-fg">{{ formatStepValue(step) }}</span>
                </li>
              </ul>
              <p
                v-else
                data-part="step-formula"
                class="mt-2 break-words font-mono text-xs leading-relaxed text-fg"
              >
                {{ step.formula }}
              </p>

              <p v-if="step.note" data-part="step-note" class="mt-2 text-xs text-fg-muted">
                {{ step.note }}
              </p>
            </li>
          </ol>
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
