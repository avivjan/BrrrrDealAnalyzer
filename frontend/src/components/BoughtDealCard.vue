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
  <div
    class="p-4 rounded-xl shadow-sm hover:shadow-md cursor-grab active:cursor-grabbing hover:scale-[1.02] transition-all duration-200 group relative overflow-hidden"
    :class="cardClass"
  >
    <!-- Badge -->
    <div
      class="absolute top-2 left-2 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border"
      :class="isBrrr ? 'bg-blue-100 text-blue-700 border-blue-200' : 'bg-orange-100 text-orange-700 border-orange-200'"
    >
      {{ isBrrr ? "🏠 BRRRR" : "💰 FLIP" }}
    </div>

    <!-- Delete Button -->
    <button
      @click.stop="onDelete(deal.id)"
      class="absolute top-2 right-2 p-1.5 rounded-full bg-red-100 text-red-600 opacity-0 group-hover:opacity-100 transition-all hover:bg-red-200 hover:scale-110 z-10"
      title="Delete Deal"
    >
      <i class="pi pi-times text-[10px] font-bold"></i>
    </button>

    <!-- Copy to AI Button -->
    <button
      @click.stop="copyToClipboard(deal)"
      class="absolute top-2 right-9 p-1.5 rounded-full opacity-0 group-hover:opacity-100 transition-all hover:scale-110 z-10"
      :class="isCopied ? 'bg-green-100 text-green-600' : 'bg-purple-100 text-purple-600 hover:bg-purple-200'"
      :title="isCopied ? 'Copied!' : 'Copy Summary for AI'"
    >
      <i class="pi text-[10px] font-bold" :class="isCopied ? 'pi-check' : 'pi-file'"></i>
    </button>

    <!-- Header: Address -->
    <div class="text-center mb-2 mt-4">
      <h3 class="font-bold text-gray-900 text-sm md:text-base leading-tight">
        {{ deal.address || "No Address" }}
      </h3>
    </div>

    <!-- Stage Badge -->
    <div class="flex justify-center mb-3">
      <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
        Stage: {{ stageConfig.name }}
      </span>
    </div>

    <!-- Task Box -->
    <div v-if="deal.task" class="bg-gray-50 rounded-lg p-2 mb-3 text-center border border-gray-200">
      <span class="text-xs text-blue-600 uppercase tracking-wider font-semibold">Current Task</span>
      <p class="text-sm text-gray-800 font-medium mt-1 line-clamp-2">{{ deal.task }}</p>
    </div>

    <!-- Key Metrics Grid -->
    <div class="grid grid-cols-2 gap-y-2 gap-x-1 text-xs text-gray-600">
      <div class="flex flex-col">
        <span class="text-[10px] text-gray-400 uppercase">Purchase</span>
        <span class="font-mono text-gray-900">{{ formatMoney(deal.purchasePrice ? deal.purchasePrice * 1000 : 0) }}</span>
      </div>
      <div class="flex flex-col text-right">
        <span class="text-[10px] text-gray-400 uppercase">Rehab</span>
        <span class="font-mono text-gray-900">{{ formatMoney(deal.rehabCost ? deal.rehabCost * 1000 : 0) }}</span>
      </div>

      <div class="flex flex-col">
        <span class="text-[10px] text-gray-400 uppercase">Cash Needed</span>
        <span class="font-mono text-orange-600">{{
          formatMoney(isBrrr ? brrrDeal?.total_cash_needed_for_deal : flipDeal?.total_cash_needed)
        }}</span>
        <span class="text-[9px] text-gray-400 uppercase mt-1">w/ Buffer</span>
        <span class="font-mono text-orange-700 text-[11px]">{{
          formatMoney(isBrrr ? brrrDeal?.total_cash_needed_for_deal_with_buffer : flipDeal?.total_cash_needed_with_buffer)
        }}</span>
      </div>

      <template v-if="isBrrr">
        <div class="flex flex-col text-right">
          <span class="text-[10px] text-gray-400 uppercase">Cash Flow</span>
          <span class="font-mono" :class="(brrrDeal?.cash_flow || 0) > 0 ? 'text-emerald-600' : 'text-red-600'">
            {{ formatMoney(brrrDeal?.cash_flow) }}
          </span>
        </div>
        <div class="flex flex-col">
          <span class="text-[10px] text-gray-400 uppercase">CoC</span>
          <span class="font-mono text-blue-600">{{ brrrDeal?.cash_on_cash ? brrrDeal.cash_on_cash.toFixed(1) + "%" : "-" }}</span>
        </div>
        <div class="flex flex-col text-right">
          <span class="text-[10px] text-gray-400 uppercase">Equity</span>
          <span class="font-mono text-emerald-600">{{ formatMoney(brrrDeal?.equity) }}</span>
        </div>
      </template>

      <template v-else>
        <div class="flex flex-col text-right">
          <span class="text-[10px] text-gray-400 uppercase">Net Profit</span>
          <span class="font-mono font-bold" :class="(flipDeal?.net_profit || 0) > 0 ? 'text-emerald-600' : 'text-red-600'">
            {{ formatMoney(flipDeal?.net_profit) }}
          </span>
        </div>
        <div class="flex flex-col">
          <span class="text-[10px] text-gray-400 uppercase">ROI</span>
          <span class="font-mono font-semibold text-blue-600">{{ flipDeal?.roi ? flipDeal.roi.toFixed(1) + "%" : "-" }}</span>
        </div>
        <div class="flex flex-col text-right">
          <span class="text-[10px] text-gray-400 uppercase">Ann. ROI</span>
          <span class="font-mono text-purple-600">{{ flipDeal?.annualized_roi ? flipDeal.annualized_roi.toFixed(1) + "%" : "-" }}</span>
        </div>
      </template>
    </div>

    <!-- Sub-stage Checklist -->
    <div v-if="subStages.length > 0" class="mt-3 pt-2 border-t border-gray-200">
      <div v-for="sub in subStages" :key="sub.id" class="flex items-center gap-2 py-0.5">
        <input
          type="checkbox"
          :checked="deal.completedSubstages[sub.id] === true"
          @click.stop="onToggleSubstage(sub.id)"
          class="w-3.5 h-3.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
        />
        <span class="text-xs text-gray-600" :class="{ 'line-through text-gray-400': deal.completedSubstages[sub.id] }">
          {{ sub.label }}
        </span>
      </div>
    </div>

    <!-- Footer Stats -->
    <div class="mt-3 pt-2 border-t border-gray-200 flex justify-between text-xs font-medium text-gray-500">
      <span>{{ deal.sqft || "-" }} sqft</span>
      <span>{{ deal.bedrooms || "-" }}bd / {{ deal.bathrooms || "-" }}ba</span>
    </div>

    <!-- Progress Bar -->
    <div class="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
      <div
        class="h-full rounded-full transition-all duration-500"
        :style="{ width: progressPercent + '%', background: 'linear-gradient(to right, #3b82f6, #10b981)' }"
      ></div>
    </div>
  </div>
</template>
