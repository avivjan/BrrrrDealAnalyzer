<script setup lang="ts">
/**
 * "Which results go in the report?" — the popup behind "Generate Report" in the
 * deal modals. One checkbox per result tile (the same tiles, captions and order
 * as the modal), all checked every time it opens; the PDF then holds one
 * section per checked result, each laid out like the tile's calculation popup.
 *
 * The overlay follows `CalculationBreakdownPopup`: teleported to `<body>`,
 * `z-[60]` above the deal modal's `z-50`, closes on the scrim, the Cancel and
 * close buttons and a document-level Escape it claims with `preventDefault`,
 * focus moved into the panel while open and restored on close, everything else
 * `inert` meanwhile.
 */
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from "vue";

import { inertOutside } from "../ui/inertOutside";
import { formatCalculationStepValueByUnit } from "./calculationStepFormat";
import { reportResultTilesForDealType } from "./reportResultTiles";

const props = withDefaults(
  defineProps<{
    open: boolean;
    dealType: "BRRRR" | "FLIP";
    /** The current analysis, for the value shown next to each result; a missing value shows no number. */
    analysis?: Record<string, unknown> | null;
  }>(),
  { analysis: null },
);

const emit = defineEmits<{
  generate: [selectedResultKeys: string[]];
  close: [];
}>();

const headingId = useId();
const overlayRoot = ref<HTMLElement | null>(null);

const reportResultTiles = computed(() => reportResultTilesForDealType(props.dealType));
// Replaced, never mutated, so the template re-reads it.
const selectedResultKeys = ref<ReadonlySet<string>>(new Set());

const selectedResultKeysInTileOrder = computed(() =>
  reportResultTiles.value.map((tile) => tile.resultKey).filter((resultKey) => selectedResultKeys.value.has(resultKey)),
);
const areAllResultsSelected = computed(() => selectedResultKeysInTileOrder.value.length === reportResultTiles.value.length);
const isAnyResultSelected = computed(() => selectedResultKeysInTileOrder.value.length > 0);

function selectAllResults() {
  selectedResultKeys.value = new Set(reportResultTiles.value.map((tile) => tile.resultKey));
}

function clearAllResults() {
  selectedResultKeys.value = new Set();
}

function toggleResult(resultKey: string) {
  const next = new Set(selectedResultKeys.value);
  if (next.has(resultKey)) next.delete(resultKey);
  else next.add(resultKey);
  selectedResultKeys.value = next;
}

function formattedResultValue(resultKey: string, unit: Parameters<typeof formatCalculationStepValueByUnit>[0]): string {
  const value = props.analysis?.[resultKey];
  return typeof value === "number" ? formatCalculationStepValueByUnit(unit, value) : "";
}

function generateReport() {
  if (!isAnyResultSelected.value) return;
  emit("generate", selectedResultKeysInTileOrder.value);
}

// -- overlay behaviour (as CalculationBreakdownPopup) ----------------------------------------------
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
    if (open) selectAllResults();
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
        data-testid="generate-report-result-picker"
        :data-deal-type="dealType"
        class="fixed inset-0 z-[60] flex items-center justify-center bg-fg/60 p-4 md:backdrop-blur-sm"
        @click.self="emit('close')"
      >
        <UiModalPanel size="md" :labelled-by="headingId" tabindex="-1" class="outline-none">
          <template #header>
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <h2 :id="headingId" class="text-base font-semibold text-fg">Generate Report</h2>
                <p class="text-xs text-fg-muted">
                  Choose the results to include. Each one is laid out like its calculation breakdown, with clickable steps.
                </p>
              </div>
              <UiIconButton label="Close" data-part="close" @click="emit('close')">
                <i class="pi pi-times" aria-hidden="true"></i>
              </UiIconButton>
            </div>
          </template>

          <div class="mb-2 flex items-center justify-between gap-2">
            <span data-part="selected-count" class="text-xs font-semibold uppercase tracking-wider text-fg-muted">
              {{ selectedResultKeysInTileOrder.length }} of {{ reportResultTiles.length }} selected
            </span>
            <div class="flex items-center gap-1">
              <UiButton data-part="select-all" variant="ghost" size="sm" :disabled="areAllResultsSelected" @click="selectAllResults">
                Select all
              </UiButton>
              <UiButton data-part="clear-all" variant="ghost" size="sm" :disabled="!isAnyResultSelected" @click="clearAllResults">
                Clear all
              </UiButton>
            </div>
          </div>

          <ul class="m-0 list-none space-y-0.5 p-0">
            <li v-for="tile in reportResultTiles" :key="tile.resultKey">
              <label
                data-part="result-option"
                :data-result-key="tile.resultKey"
                class="flex min-h-9 cursor-pointer items-center gap-3 rounded-ctl px-2 py-1.5 transition-colors duration-fast ease-standard hover:bg-surface-2"
              >
                <input
                  type="checkbox"
                  data-part="result-option-input"
                  :checked="selectedResultKeys.has(tile.resultKey)"
                  class="h-4 w-4 shrink-0 rounded border-line accent-primary"
                  @change="toggleResult(tile.resultKey)"
                />
                <span data-part="result-option-label" class="min-w-0 flex-1 truncate text-sm text-fg">{{ tile.tileLabel }}</span>
                <span data-part="result-option-value" class="numeric tabular text-sm text-fg-muted">
                  {{ formattedResultValue(tile.resultKey, tile.unit) }}
                </span>
              </label>
            </li>
          </ul>

          <template #footer>
            <div class="flex items-center justify-end gap-2">
              <UiButton data-part="cancel" variant="ghost" size="sm" @click="emit('close')">Cancel</UiButton>
              <UiButton data-part="generate" variant="primary" size="sm" :disabled="!isAnyResultSelected" @click="generateReport">
                <i class="pi pi-file-pdf text-base" aria-hidden="true"></i>
                Generate PDF
              </UiButton>
            </div>
          </template>
        </UiModalPanel>
      </div>
    </UiTransition>
  </Teleport>
</template>
