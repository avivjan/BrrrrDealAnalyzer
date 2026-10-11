<script setup lang="ts">
/**
 * "Estimate ARV with Claude": the user confirms the address and writes a note
 * about the situation; the backend asks Claude (live web search) for an ARV
 * using the FLIP or BRRRR lens and returns a fixed template, rendered here.
 * Nothing changes on the deal until **Apply** — the parent writes the numbers.
 *
 * Every piece of Claude's answer is rendered as text through Vue's escaping
 * (no `v-html`); links are http(s) only (the backend drops anything else).
 *
 * The overlay follows `GenerateReportResultPickerPopup`: teleported to
 * `<body>`, `z-[60]` above the deal modal's `z-50`, closes on the scrim, the
 * close buttons and a document-level Escape it claims with `preventDefault`,
 * focus moved into the panel while open and restored on close, everything
 * else `inert` meanwhile.
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { inertOutside } from "../ui/inertOutside";
import api from "../../api";
import type { DealInputModel } from "../../types";
import type { ArvComparableProperty, ArvEstimateReq, ArvEstimateRes } from "../../types/arvEstimate";
import UiDataTable, { type DataTableColumn } from "../ui/UiDataTable.vue";
import { toNumber } from "../../utils/dealUtils";
import { formatMoney } from "../../utils/money";

const props = defineProps<{
  isOpen: boolean;
  dealType: "BRRRR" | "FLIP";
  deal: DealInputModel;
}>();

const emit = defineEmits<{
  close: [];
  "apply-arv-estimate": [arvEstimate: ArvEstimateRes];
}>();

const propertyAddress = ref("");
const investorSituationNote = ref("");
const isEstimateInProgress = ref(false);
const estimateErrorMessage = ref<string | null>(null);
const arvEstimate = ref<ArvEstimateRes | null>(null);

const INVESTOR_SITUATION_NOTE_MAX_LENGTH = 2000;
/** Opus with live web search; shown before every click so the spend is never a surprise. */
const ARV_ESTIMATE_COST_NOTE = "Each estimate costs roughly $0.10–0.50 in Claude API usage.";

const isBrrrr = computed(() => props.dealType === "BRRRR");
const strategyLabel = computed(() => (isBrrrr.value ? "BRRRR — appraisal lens (3–4 strongest comps)" : "Flip — conservative market lens"));
const applyButtonLabel = computed(() =>
  isBrrrr.value ? "Apply to ARV and Lowest ARV" : "Apply to Projected Sale Price",
);

const overlayRoot = ref<HTMLElement | null>(null);

function onDocumentKeydown(event: KeyboardEvent) {
  if (event.key !== "Escape" || event.defaultPrevented) return;
  event.preventDefault();
  emit("close");
}

function listenForEscape(isOpen: boolean) {
  if (typeof document === "undefined") return;
  document.removeEventListener("keydown", onDocumentKeydown);
  if (isOpen) document.addEventListener("keydown", onDocumentKeydown);
}

let restoreFocusTo: HTMLElement | null = null;
let releaseInert: (() => void) | null = null;

onBeforeUnmount(() => {
  listenForEscape(false);
  releaseInert?.();
  releaseInert = null;
});

watch(
  () => props.isOpen,
  async (isOpen) => {
    if (isOpen && !propertyAddress.value.trim()) propertyAddress.value = props.deal.address ?? "";
    if (typeof document === "undefined") return;
    listenForEscape(isOpen);
    if (isOpen) {
      restoreFocusTo = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      await nextTick();
      overlayRoot.value?.querySelector<HTMLElement>('[data-ui="modal-panel"]')?.focus();
      releaseInert?.();
      releaseInert = overlayRoot.value ? inertOutside(overlayRoot.value) : null;
    } else {
      releaseInert?.();
      releaseInert = null;
      restoreFocusTo?.focus();
      restoreFocusTo = null;
    }
  },
  { immediate: true },
);

/** The form keeps price and rehab in thousands; the API takes plain dollars. */
function thousandsToDollars(valueInThousands: unknown): number | null {
  const thousands = toNumber(valueInThousands);
  return thousands == null || thousands <= 0 ? null : thousands * 1000;
}

function positiveNumberOrNull(value: unknown): number | null {
  const number = toNumber(value);
  return number == null || number <= 0 ? null : number;
}

function buildArvEstimateRequest(): ArvEstimateReq {
  return {
    deal_type: props.dealType,
    property_address: propertyAddress.value.trim(),
    investor_situation_note: investorSituationNote.value.trim(),
    subject_square_feet: positiveNumberOrNull(props.deal.sqft),
    subject_bedrooms: positiveNumberOrNull(props.deal.bedrooms),
    subject_bathrooms: positiveNumberOrNull(props.deal.bathrooms),
    purchase_price: thousandsToDollars(props.deal.purchasePrice),
    rehab_budget: thousandsToDollars(props.deal.rehabCost),
  };
}

async function requestArvEstimate() {
  if (propertyAddress.value.trim().length < 3) {
    estimateErrorMessage.value = "Enter the property address first.";
    return;
  }
  isEstimateInProgress.value = true;
  estimateErrorMessage.value = null;
  arvEstimate.value = null;
  try {
    arvEstimate.value = await api.estimateArvWithClaude(buildArvEstimateRequest());
  } catch (error: any) {
    const detail = error?.response?.data?.detail;
    const httpStatus = error?.response?.status;
    estimateErrorMessage.value =
      typeof detail === "string"
        ? detail
        : httpStatus
          ? `The ARV estimate failed (HTTP ${httpStatus}); try again.`
          : "The ARV estimate failed; try again.";
  } finally {
    isEstimateInProgress.value = false;
  }
}

function applyArvEstimate() {
  if (!arvEstimate.value) return;
  emit("apply-arv-estimate", arvEstimate.value);
  emit("close");
}

function formatOptionalNumber(value: number | null | undefined, suffix = ""): string {
  return value == null ? "—" : `${value.toLocaleString("en-US", { maximumFractionDigits: 1 })}${suffix}`;
}

function formatOptionalMoney(value: number | null | undefined): string {
  return value == null ? "—" : formatMoney(Math.round(value));
}

const MARKET_PACE_LABEL: Record<ArvEstimateRes["market_pace_verdict"], string> = {
  FAST: "Fast market",
  NORMAL: "Normal pace",
  SLOW: "Slow market",
  UNKNOWN: "Pace unknown",
};

const WEIGHT_IN_VALUATION_TONE = { PRIMARY: "primary", SUPPORTING: "neutral", EXCLUDED: "warning" } as const;

const confidenceTone = computed(() => {
  const score = arvEstimate.value?.confidence_score_1_to_10 ?? 0;
  return score >= 7 ? "positive" : score >= 4 ? "warning" : "negative";
});

const comparableColumns: DataTableColumn[] = [
  { key: "address", label: "Address" },
  { key: "distance", label: "Dist", align: "right", numeric: true },
  { key: "date", label: "Date", numeric: true },
  { key: "price", label: "Price", align: "right", numeric: true },
  { key: "bedsBaths", label: "Bd/Ba", align: "center", numeric: true },
  { key: "squareFeet", label: "SqFt", align: "right", numeric: true },
  { key: "yearBuilt", label: "Built", align: "right", numeric: true },
  { key: "pricePerSquareFoot", label: "$/SqFt", align: "right", numeric: true },
  { key: "daysOnMarket", label: "DOM", align: "right", numeric: true },
  { key: "adjustedValue", label: "Adjusted", align: "right", numeric: true },
  { key: "weight", label: "Weight", align: "center" },
];

function toComparableRow(comparable: ArvComparableProperty, rowIndex: number) {
  return {
    rowKey: `${rowIndex}-${comparable.address}`,
    address: comparable.address,
    sourceUrl: comparable.source_url,
    condition: comparable.renovation_condition,
    adjustmentExplanation: comparable.adjustment_explanation,
    distance: formatOptionalNumber(comparable.distance_from_subject_in_miles, " mi"),
    date: comparable.sale_or_list_date ?? "—",
    price: formatOptionalMoney(comparable.sale_or_list_price),
    bedsBaths: `${formatOptionalNumber(comparable.bedrooms)}/${formatOptionalNumber(comparable.bathrooms)}`,
    squareFeet: formatOptionalNumber(comparable.square_feet),
    yearBuilt: comparable.year_built ?? "—",
    pricePerSquareFoot: formatOptionalMoney(comparable.price_per_square_foot),
    daysOnMarket: formatOptionalNumber(comparable.days_on_market),
    adjustedValue: formatOptionalMoney(comparable.adjusted_value_for_subject),
    weight: comparable.weight_in_valuation,
  };
}

const soldComparableRows = computed(() => (arvEstimate.value?.sold_comparables ?? []).map(toComparableRow));
const activeOrPendingComparableRows = computed(() =>
  (arvEstimate.value?.active_or_pending_comparables ?? []).map(toComparableRow),
);
</script>

<template>
  <Teleport to="body">
  <UiTransition preset="modalEnterOnly">
    <div
      v-if="isOpen"
      ref="overlayRoot"
      data-overlay
      data-testid="arvEstimate.root"
      :data-deal-type="dealType"
      class="fixed inset-0 z-[60] flex items-center justify-center bg-fg/60 p-4 md:backdrop-blur-sm"
      @click.self="emit('close')"
    >
      <UiModalPanel size="xl" labelled-by="arv-estimate-modal-title" tabindex="-1" class="outline-none">
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <h3 id="arv-estimate-modal-title" class="min-w-0 text-base font-semibold text-fg md:text-lg">
              <i class="pi pi-sparkles mr-1 text-primary" aria-hidden="true"></i> Estimate ARV with Claude
            </h3>
            <UiIconButton data-testid="arvEstimate.close" label="Close" size="md" @click="emit('close')">
              <i class="pi pi-times text-lg" aria-hidden="true"></i>
            </UiIconButton>
          </div>
        </template>

        <div class="space-y-4">
          <p class="text-sm text-fg-muted">
            Strategy: <span data-testid="arvEstimate.strategy" class="font-medium text-fg">{{ strategyLabel }}</span>
          </p>
          <p data-testid="arvEstimate.costNote" class="-mt-3 text-xs text-fg-muted">
            <i class="pi pi-info-circle mr-1" aria-hidden="true"></i>{{ ARV_ESTIMATE_COST_NOTE }}
          </p>

          <UiField>
            <template #label>Property Address *</template>
            <template #default="{ id, describedBy }">
              <input
                data-testid="arvEstimate.address"
                v-model="propertyAddress"
                :id="id"
                :aria-describedby="describedBy"
                type="text"
                maxlength="300"
                class="ui-input"
                placeholder="123 Main St, City, ST 00000"
              />
            </template>
          </UiField>

          <UiField>
            <template #label>Situation note</template>
            <template #default="{ id, describedBy }">
              <textarea
                data-testid="arvEstimate.note"
                v-model="investorSituationNote"
                :id="id"
                :aria-describedby="describedBy"
                :maxlength="INVESTOR_SITUATION_NOTE_MAX_LENGTH"
                rows="3"
                class="ui-input min-h-[5rem] py-2"
                placeholder="Scope of work, condition, layout changes (e.g. adding a bathroom), what you know about the block…"
              ></textarea>
            </template>
          </UiField>

          <div
            v-if="estimateErrorMessage"
            data-testid="arvEstimate.error"
            role="alert"
            class="rounded-ctl bg-negative/10 p-3 text-sm font-medium text-negative"
          >
            {{ estimateErrorMessage }}
          </div>

          <div v-if="isEstimateInProgress" data-testid="arvEstimate.loading" role="status" class="space-y-2">
            <p class="text-sm text-fg-muted">
              <i class="pi pi-spin pi-spinner mr-1" aria-hidden="true"></i>
              Claude is pulling comps and adjusting them — usually 1–3 minutes. Keep this open.
            </p>
            <UiSkeleton :lines="4" />
          </div>

          <section v-if="arvEstimate" data-testid="arvEstimate.result" class="space-y-4" aria-label="ARV estimate">
            <div class="grid grid-cols-2 gap-2 md:grid-cols-5">
              <UiStatTile data-testid="arvEstimate.result.targetArv" label="Target ARV" size="md">
                {{ formatOptionalMoney(arvEstimate.target_arv) }}
              </UiStatTile>
              <UiStatTile data-testid="arvEstimate.result.range" label="Range">
                {{ formatOptionalMoney(arvEstimate.estimated_arv_range_low) }} – {{ formatOptionalMoney(arvEstimate.estimated_arv_range_high) }}
              </UiStatTile>
              <UiStatTile data-testid="arvEstimate.result.conservativeLowestArv" :label="isBrrrr ? 'Conservative appraisal' : 'Conservative sale'">
                {{ formatOptionalMoney(arvEstimate.conservative_lowest_arv) }}
              </UiStatTile>
              <UiStatTile data-testid="arvEstimate.result.confidence" label="Confidence" :tone="confidenceTone">
                {{ arvEstimate.confidence_score_1_to_10 }}/10
              </UiStatTile>
              <UiStatTile data-testid="arvEstimate.result.daysOnMarket" label="Avg DOM (sold)">
                {{ formatOptionalNumber(arvEstimate.average_days_on_market_of_sold_comparables, " days") }}
                <template #hint>
                  {{ MARKET_PACE_LABEL[arvEstimate.market_pace_verdict] }} · median {{ formatOptionalNumber(arvEstimate.median_days_on_market_of_sold_comparables) }}
                </template>
              </UiStatTile>
            </div>

            <div class="rounded-card bg-surface-2 p-3 text-sm text-fg" data-testid="arvEstimate.result.marketLogic">
              <h4 class="mb-1 font-semibold">Market logic</h4>
              <p class="whitespace-pre-line">{{ arvEstimate.market_logic }}</p>
            </div>

            <div v-for="table in [
              { title: 'Sold comps', rows: soldComparableRows, testId: 'arvEstimate.result.soldComparables' },
              { title: 'Active / pending comps', rows: activeOrPendingComparableRows, testId: 'arvEstimate.result.activeComparables' },
            ]" :key="table.testId" class="space-y-1">
              <h4 class="text-sm font-semibold text-fg">{{ table.title }}</h4>
              <div class="overflow-x-auto">
                <UiDataTable :data-testid="table.testId" :columns="comparableColumns" :rows="table.rows" row-key="rowKey" dense :caption="table.title">
                  <template #cell-address="{ row }">
                    <a
                      v-if="row.sourceUrl"
                      :href="String(row.sourceUrl)"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="text-primary underline-offset-2 hover:underline"
                    >{{ row.address }}</a>
                    <span v-else>{{ row.address }}</span>
                    <span class="block text-xs text-fg-muted">{{ row.condition }}</span>
                    <span v-if="row.adjustmentExplanation" class="block text-xs text-fg-muted">{{ row.adjustmentExplanation }}</span>
                  </template>
                  <template #cell-weight="{ row }">
                    <UiBadge :tone="WEIGHT_IN_VALUATION_TONE[row.weight as keyof typeof WEIGHT_IN_VALUATION_TONE]" size="sm">{{ String(row.weight).toLowerCase() }}</UiBadge>
                  </template>
                  <template #empty>None found.</template>
                </UiDataTable>
              </div>
            </div>

            <div v-if="arvEstimate.data_caveats.length" data-testid="arvEstimate.result.caveats" class="rounded-card border-ui border-warning/40 bg-warning/5 p-3 text-sm">
              <h4 class="mb-1 font-semibold text-fg">Caveats</h4>
              <ul class="list-disc space-y-0.5 pl-5 text-fg">
                <li v-for="(caveat, caveatIndex) in arvEstimate.data_caveats" :key="caveatIndex">{{ caveat }}</li>
              </ul>
            </div>

            <details v-if="arvEstimate.discarded_comparables.length || arvEstimate.source_urls.length" class="text-sm text-fg">
              <summary class="cursor-pointer font-semibold">Discarded comps and sources</summary>
              <ul v-if="arvEstimate.discarded_comparables.length" class="mt-2 list-disc space-y-0.5 pl-5" data-testid="arvEstimate.result.discarded">
                <li v-for="(discarded, discardedIndex) in arvEstimate.discarded_comparables" :key="discardedIndex">
                  {{ discarded.address }} — {{ discarded.reason_for_discarding }}
                </li>
              </ul>
              <ul v-if="arvEstimate.source_urls.length" class="mt-2 space-y-0.5 break-all">
                <li v-for="sourceUrl in arvEstimate.source_urls" :key="sourceUrl">
                  <a :href="sourceUrl" target="_blank" rel="noopener noreferrer" class="text-primary underline-offset-2 hover:underline">{{ sourceUrl }}</a>
                </li>
              </ul>
            </details>

            <p class="text-xs text-fg-muted">
              AI estimate from public listings — verify the comps before you rely on it.
            </p>
          </section>
        </div>

        <template #footer>
          <div class="flex flex-wrap items-center justify-end gap-2">
            <UiButton data-testid="arvEstimate.cancel" variant="ghost" @click="emit('close')">Close</UiButton>
            <UiButton
              data-testid="arvEstimate.submit"
              :variant="arvEstimate ? 'secondary' : 'primary'"
              :disabled="isEstimateInProgress"
              @click="requestArvEstimate"
            >
              <i v-if="isEstimateInProgress" class="pi pi-spin pi-spinner" aria-hidden="true"></i>
              {{ isEstimateInProgress ? "Estimating…" : arvEstimate ? "Estimate again" : "Estimate ARV" }}
            </UiButton>
            <UiButton v-if="arvEstimate" data-testid="arvEstimate.apply" @click="applyArvEstimate">
              {{ applyButtonLabel }}
            </UiButton>
          </div>
        </template>
      </UiModalPanel>
    </div>
  </UiTransition>
  </Teleport>
</template>
