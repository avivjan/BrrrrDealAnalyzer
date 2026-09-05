<script setup lang="ts">
import { computed, ref } from "vue";
import type { BoughtDealRes, BoughtBrrrDealRes, BoughtFlipDealRes } from "../types";
import { formatDealForClipboard } from "../utils/dealUtils";
import { useBoughtDealStore } from "../stores/boughtDealStore";
import { usePipelineTemplateStore } from "../stores/pipelineTemplateStore";
import { resolveStage, getSubStagesForStage, canAdvance } from "../config/boughtDealStages";

const props = defineProps<{
  deal: BoughtDealRes;
}>();

const emit = defineEmits<{
  (e: "delete", id: string): void;
}>();

const store = useBoughtDealStore();
const pipelineStore = usePipelineTemplateStore();
const isCopied = ref(false);

const isBrrr = computed(() => !props.deal.deal_type || props.deal.deal_type === "BRRRR");
const isFlip = computed(() => props.deal.deal_type === "FLIP");

const brrrDeal = computed(() => isBrrr.value ? (props.deal as BoughtBrrrDealRes) : null);
const flipDeal = computed(() => isFlip.value ? (props.deal as BoughtFlipDealRes) : null);

const dealType = computed(() => (props.deal.deal_type || "BRRRR") as 'FLIP' | 'BRRRR');
const pipeline = computed(() => pipelineStore.pipelineFor(dealType.value));
const stageConfig = computed(() => resolveStage(pipeline.value, props.deal.boughtStage));
const subStages = computed(() => getSubStagesForStage(pipeline.value, props.deal.boughtStage));
const allSubstagesComplete = computed(() =>
  canAdvance(pipeline.value, props.deal.boughtStage, props.deal.completedSubstages),
);
const progressPercent = computed(() => {
  const stages = pipeline.value.stages;
  const currentIdx = stages.findIndex(s => s.id === props.deal.boughtStage);
  if (currentIdx === -1) return 0;
  return ((currentIdx) / (stages.length - 1)) * 100;
});

const stageColorClass = computed(() => {
  const stages = pipeline.value.stages;
  const currentIdx = stages.findIndex(s => s.id === props.deal.boughtStage);
  const ratio = stages.length > 1 ? currentIdx / (stages.length - 1) : 0;
  if (ratio < 0.33) return "border-l-4 border-l-blue-500";
  if (ratio < 0.66) return "border-l-4 border-l-emerald-500";
  return "border-l-4 border-l-green-600";
});

const cardClass = computed(() => {
  let base = stageColorClass.value + " bg-white border border-gray-100";
  if (isFlip.value) base += " bg-orange-50/30";
  if (allSubstagesComplete.value && subStages.value.length > 0) base += " ring-2 ring-emerald-300";
  return base;
});

const formatMoney = (val?: number) => val ? `$${Math.round(val).toLocaleString()}` : "-";

const copyToClipboard = async (deal: BoughtDealRes) => {
  try {
    const text = formatDealForClipboard(deal);
    await navigator.clipboard.writeText(text);
    isCopied.value = true;
    setTimeout(() => { isCopied.value = false; }, 2000);
  } catch (err) {
    console.error("Failed to copy to clipboard", err);
  }
};

const onDelete = (id: string) => emit("delete", id);

const onToggleSubstage = (substageId: string) => {
  store.toggleSubstage(props.deal.id, substageId);
};
</script>

<template>
  <UiCard
    tone="surface"
    padding="md"
    :class="[cardClass, 'border-line', stageColorClass, 'ring-positive/40']"
    class="group relative overflow-hidden cursor-grab active:cursor-grabbing hover:shadow-2"
  >
    <!-- Badge -->
    <UiBadge
      :tone="isBrrr ? 'primary' : 'warning'"
      size="sm"
      class="absolute top-2 left-2 z-10 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide"
    >
      {{ isBrrr ? "🏠 BRRRR" : "💰 FLIP" }}
    </UiBadge>

    <!--
      One action row instead of two hand-placed `right-*` offsets; the children
      keep their document order (delete, copy) and `flex-row-reverse` puts them
      on screen in the order the absolute offsets used to: copy, delete.
    -->
    <div
      data-part="card-actions"
      class="absolute top-2 right-2 z-10 flex flex-row-reverse items-center gap-1 opacity-0 transition-opacity duration-fast ease-standard group-hover:opacity-100 focus-within:opacity-100 touch:opacity-100"
    >
      <!-- Delete Button -->
      <UiIconButton
        data-testid="boughtcard.delete"
        @click.stop="onDelete(deal.id)"
        label="Delete Deal"
        variant="danger"
        size="sm"
        title="Delete Deal"
      >
        <i class="pi pi-times text-xs" aria-hidden="true"></i>
      </UiIconButton>

      <!-- Copy to AI Button -->
      <UiIconButton
        data-testid="boughtcard.copy"
        @click.stop="copyToClipboard(deal)"
        :label="isCopied ? 'Copied!' : 'Copy Summary for AI'"
        :class="isCopied ? 'text-positive' : ''"
        variant="ghost"
        size="sm"
        :title="isCopied ? 'Copied!' : 'Copy Summary for AI'"
      >
        <!-- Both glyphs are always rendered and crossfade, so the button does
             not reflow the row the instant the clipboard write resolves. -->
        <span class="grid h-4 w-4 place-items-center">
          <i
            class="pi pi-file col-start-1 row-start-1 text-xs transition-opacity duration-fast ease-standard"
            :class="isCopied ? 'opacity-0' : 'opacity-100'"
            aria-hidden="true"
          ></i>
          <i
            class="pi pi-check col-start-1 row-start-1 text-xs transition-opacity duration-fast ease-standard"
            :class="isCopied ? 'opacity-100' : 'opacity-0'"
            aria-hidden="true"
          ></i>
        </span>
      </UiIconButton>
    </div>

    <!-- Header: Address -->
    <div class="text-center mb-2 mt-6">
      <h3 class="truncate text-sm md:text-base font-medium leading-tight text-fg">
        {{ deal.address || "No Address" }}
      </h3>
    </div>

    <!-- Stage Badge -->
    <div class="flex justify-center mb-3">
      <UiBadge tone="info" size="sm" class="max-w-full">
        <span class="truncate">Stage: {{ stageConfig.name }}</span>
      </UiBadge>
    </div>

    <!-- Task Box -->
    <div v-if="deal.task" class="bg-surface-muted rounded-ctl p-2 mb-3 text-center border border-line">
      <span class="text-xs text-primary uppercase tracking-wider font-semibold">Current Task</span>
      <p class="text-sm text-fg font-medium mt-1 line-clamp-2">{{ deal.task }}</p>
    </div>

    <!-- Key Metrics Grid -->
    <div class="grid grid-cols-2 gap-y-2 gap-x-2 text-xs text-fg-muted">
      <div class="flex flex-col min-w-0">
        <span class="text-[10px] text-fg-muted uppercase tracking-wide">Purchase</span>
        <span class="tabular text-fg font-medium">{{ formatMoney(deal.purchasePrice ? deal.purchasePrice * 1000 : 0) }}</span>
      </div>
      <div class="flex flex-col min-w-0 text-right">
        <span class="text-[10px] text-fg-muted uppercase tracking-wide">Rehab</span>
        <span class="tabular text-fg font-medium">{{ formatMoney(deal.rehabCost ? deal.rehabCost * 1000 : 0) }}</span>
      </div>

      <div class="flex flex-col min-w-0">
        <span class="text-[10px] text-fg-muted uppercase tracking-wide">Cash Needed</span>
        <span class="tabular text-warning font-medium">{{
          formatMoney(isBrrr ? brrrDeal?.total_cash_needed_for_deal : flipDeal?.total_cash_needed)
        }}</span>
        <span class="text-[9px] text-fg-muted uppercase tracking-wide mt-1">w/ Buffer</span>
        <span class="tabular text-warning text-[11px]">{{
          formatMoney(isBrrr ? brrrDeal?.total_cash_needed_for_deal_with_buffer : flipDeal?.total_cash_needed_with_buffer)
        }}</span>
      </div>

      <template v-if="isBrrr">
        <div class="flex flex-col min-w-0 text-right">
          <span class="text-[10px] text-fg-muted uppercase tracking-wide">Cash Flow</span>
          <span class="tabular font-medium" :class="(brrrDeal?.cash_flow || 0) > 0 ? 'text-positive' : 'text-negative'">
            {{ formatMoney(brrrDeal?.cash_flow) }}
          </span>
        </div>
        <div class="flex flex-col min-w-0">
          <span class="text-[10px] text-fg-muted uppercase tracking-wide">CoC</span>
          <span class="tabular text-primary font-medium">{{ brrrDeal?.cash_on_cash ? brrrDeal.cash_on_cash.toFixed(1) + "%" : "-" }}</span>
        </div>
        <div class="flex flex-col min-w-0 text-right">
          <span class="text-[10px] text-fg-muted uppercase tracking-wide">Equity</span>
          <span class="tabular text-positive font-medium">{{ formatMoney(brrrDeal?.equity) }}</span>
        </div>
      </template>

      <template v-else>
        <div class="flex flex-col min-w-0 text-right">
          <span class="text-[10px] text-fg-muted uppercase tracking-wide">Net Profit</span>
          <span class="tabular font-bold" :class="(flipDeal?.net_profit || 0) > 0 ? 'text-positive' : 'text-negative'">
            {{ formatMoney(flipDeal?.net_profit) }}
          </span>
        </div>
        <div class="flex flex-col min-w-0">
          <span class="text-[10px] text-fg-muted uppercase tracking-wide">ROI</span>
          <span class="tabular font-semibold text-primary">{{ flipDeal?.roi ? flipDeal.roi.toFixed(1) + "%" : "-" }}</span>
        </div>
        <div class="flex flex-col min-w-0 text-right">
          <span class="text-[10px] text-fg-muted uppercase tracking-wide">Ann. ROI</span>
          <span class="tabular text-fg font-medium">{{ flipDeal?.annualized_roi ? flipDeal.annualized_roi.toFixed(1) + "%" : "-" }}</span>
        </div>
      </template>
    </div>

    <!-- Sub-stage Checklist -->
    <div v-if="subStages.length > 0" class="mt-3 pt-2 border-t border-line">
      <div v-for="sub in subStages" :key="sub.id" :data-testid="`boughtcard.substage.${sub.id}`" class="flex items-center gap-2 py-0.5">
        <input
          type="checkbox"
          :data-testid="`boughtcard.substage.${sub.id}.input`"
          :checked="deal.completedSubstages[sub.id] === true"
          @click.stop="onToggleSubstage(sub.id)"
          class="h-4 w-4 shrink-0 rounded accent-primary cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        />
        <span class="text-xs text-fg-muted" :class="{ 'line-through': deal.completedSubstages[sub.id] }">
          {{ sub.label }}
        </span>
      </div>
    </div>

    <!-- Footer Stats -->
    <div class="mt-3 pt-2 border-t border-line flex justify-between text-xs font-medium text-fg-muted tabular">
      <span>{{ deal.sqft || "-" }} sqft</span>
      <span>{{ deal.bedrooms || "-" }}bd / {{ deal.bathrooms || "-" }}ba</span>
    </div>

    <!-- Progress Bar -->
    <div class="mt-2 h-1.5 bg-line rounded-full overflow-hidden">
      <div
        class="h-full rounded-full bg-primary transition-[width] duration-slow ease-standard"
        :style="{ width: progressPercent + '%' }"
      ></div>
    </div>
  </UiCard>
</template>

