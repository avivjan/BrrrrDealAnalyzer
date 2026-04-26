<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import type { ActiveDealRes, BrrrDealRes, FlipDealRes } from "../types";
import { formatDealForClipboard } from "../utils/dealUtils";
import BreakdownTooltip from "./ui/BreakdownTooltip.vue";

const props = defineProps<{
  deal: ActiveDealRes;
}>();

const emit = defineEmits<{
  (e: "delete", id: string): void;
  (e: "duplicate", id: string): void;
  (e: "moveToBought", id: string): void;
  (e: "moveToBought", id: string): void;
}>();

const isCopied = ref(false);

const isBrrr = computed(
  () => !props.deal.deal_type || props.deal.deal_type === "BRRRR",
);
const isFlip = computed(() => props.deal.deal_type === "FLIP");

// Casted helpers
const brrrDeal = computed(() =>
  isBrrr.value ? (props.deal as BrrrDealRes) : null,
);
const flipDeal = computed(() =>
  isFlip.value ? (props.deal as FlipDealRes) : null,
);

const copyToClipboard = async (deal: ActiveDealRes) => {
  try {
    const text = formatDealForClipboard(deal);
    await navigator.clipboard.writeText(text);
    console.log("Deal details copied to clipboard");
    isCopied.value = true;
    setTimeout(() => {
      isCopied.value = false;
    }, 2000);
  } catch (err) {
    console.error("Failed to copy to clipboard", err);
  }
};

onMounted(() => {
  // console.log('Component: DealCard mounted', props.deal.id); // Too verbose for every card
});

const onDelete = (id: string) => {
  console.log("Component: DealCard - delete clicked for deal:", id);
  emit("delete", id);
};

const onDuplicate = (id: string) => {
  console.log("Component: DealCard - duplicate clicked for deal:", id);
  emit("duplicate", id);
};
const onMoveToBought = (id: string) => {
  console.log("Component: DealCard - move to bought clicked for deal:", id);
  emit("moveToBought", id);
};


const stageColors = {
  1: "border-l-4 border-l-blue-500 bg-white border border-gray-100", // New
  2: "border-l-4 border-l-yellow-500 bg-white border border-gray-100", // Working
  3: "border-l-4 border-l-emerald-500 bg-white border border-gray-100", // Brought
  4: "border-l-4 border-l-purple-500 bg-white border border-gray-100", // Keep
  5: "border-l-4 border-l-gray-400 bg-gray-50 border border-gray-100", // Dead
};

const cardClass = computed(() => {
  // Base stage color
  let base =
    stageColors[props.deal.stage as keyof typeof stageColors] || stageColors[1];

  // Type styling
  if (isFlip.value) {
    // Add orange tint or border style?
    // Tailwind classes can be appended
    base += " bg-orange-50/30"; // Subtle orange tint
  }
  return base;
});

const formatMoney = (val?: number) =>
  val ? `$${Math.round(val).toLocaleString()}` : "-";

/**
 * Look up a breakdown formula by metric key. Falls back to undefined so the
 * tooltip auto-hides when the analyzer didn't return a formula (e.g. on
 * legacy stored deals before this feature shipped).
 */
const breakdownFor = (key: string): string | undefined =>
  ((props.deal as any)?.breakdowns as Record<string, string> | undefined)?.[key];
</script>

<template>
  <div
    class="p-4 rounded-xl shadow-sm hover:shadow-md cursor-grab active:cursor-grabbing hover:scale-[1.02] transition-all duration-200 group relative overflow-hidden"
    :class="cardClass"
  >
    <!-- Badge -->
    <div
      class="absolute top-2 left-2 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border"
      :class="
        isBrrr
          ? 'bg-blue-100 text-blue-700 border-blue-200'
          : 'bg-orange-100 text-orange-700 border-orange-200'
      "
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

    <!-- Duplicate Button -->
    <button
      @click.stop="onDuplicate(deal.id)"
      class="absolute top-2 right-9 p-1.5 rounded-full bg-blue-100 text-blue-600 opacity-0 group-hover:opacity-100 transition-all hover:bg-blue-200 hover:scale-110 z-10"
      title="Duplicate Deal"
    >
      <i class="pi pi-copy text-[10px] font-bold"></i>
    </button>
    <!-- Move to Bought Button (only for Brought stage) -->
    <button
      v-if="deal.stage === 3"
      @click.stop="onMoveToBought(deal.id)"
      class="absolute top-2 right-[5.75rem] p-1.5 rounded-full bg-emerald-100 text-emerald-600 opacity-0 group-hover:opacity-100 transition-all hover:bg-emerald-200 hover:scale-110 z-10"
      title="Move to Bought Deals"
    >
      <i class="pi pi-arrow-right text-[10px] font-bold"></i>
    </button>

    <!-- Copy to AI Button -->
    <button
      @click.stop="copyToClipboard(deal)"
      class="absolute top-2 p-1.5 rounded-full opacity-0 group-hover:opacity-100 transition-all hover:scale-110 z-10"
      :class="[
        deal.stage === 3 ? 'right-[8.25rem]' : 'right-16',
        isCopied
          ? 'bg-green-100 text-green-600'
          : 'bg-purple-100 text-purple-600 hover:bg-purple-200'
      ]"
      :title="isCopied ? 'Copied!' : 'Copy Summary for AI'"
    >
      <i
        class="pi text-[10px] font-bold"
        :class="isCopied ? 'pi-check' : 'pi-file'"
      ></i>
    </button>

    <!-- Header: Address -->
    <div class="text-center mb-3 mt-4">
      <h3 class="font-bold text-gray-900 text-sm md:text-base leading-tight">
        {{ deal.address || "No Address" }}
      </h3>
    </div>

    <!-- Task Box -->
    <div
      v-if="deal.task"
      class="bg-gray-50 rounded-lg p-2 mb-3 text-center border border-gray-200"
    >
      <span class="text-xs text-blue-600 uppercase tracking-wider font-semibold"
        >Current Task</span
      >
      <p class="text-sm text-gray-800 font-medium mt-1 line-clamp-2">
        {{ deal.task }}
      </p>
    </div>

    <!-- Key Metrics Grid -->
    <div class="grid grid-cols-2 gap-y-2 gap-x-1 text-xs text-gray-600">
      <!-- Row 1: Purchase & Rehab -->
      <div class="flex flex-col">
        <span class="text-[10px] text-gray-400 uppercase">Purchase</span>
        <span class="font-mono text-gray-900">{{
          formatMoney(deal.purchasePrice ? deal.purchasePrice * 1000 : 0)
        }}</span>
      </div>
      <div class="flex flex-col text-right">
        <span class="text-[10px] text-gray-400 uppercase">Rehab</span>
        <span class="font-mono text-gray-900">{{
          formatMoney(deal.rehabCost ? deal.rehabCost * 1000 : 0)
        }}</span>
      </div>

      <!-- Row 2: Cash Needed (with and without buffer) -->
      <div class="flex flex-col">
        <span class="text-[10px] text-gray-400 uppercase">Cash Needed</span>
        <span class="font-mono text-orange-600">{{
          formatMoney(
            isBrrr
              ? brrrDeal?.total_cash_needed_for_deal
              : flipDeal?.total_cash_needed,
          )
        }}</span>
        <span class="text-[9px] text-gray-400 uppercase mt-1">w/ Buffer</span>
        <span class="font-mono text-orange-700 text-[11px]">{{
          formatMoney(
            isBrrr
              ? brrrDeal?.total_cash_needed_for_deal_with_buffer
              : flipDeal?.total_cash_needed_with_buffer,
          )
        }}</span>
      </div>

      <!-- Type Specific Rows -->
      <template v-if="isBrrr">
        <div class="flex flex-col text-right">
          <span class="text-[10px] text-gray-400 uppercase">Cash Out</span>
          <span
            class="font-mono font-semibold"
            :class="
              (brrrDeal?.cash_out || 0) >= 0
                ? 'text-emerald-600'
                : 'text-red-500'
            "
          >
            {{ formatMoney(brrrDeal?.cash_out) }}
          </span>
        </div>
        <div class="flex flex-col">
          <span class="text-[10px] text-gray-400 uppercase"
            >Cash Out Routi</span
          >
          <span
            class="font-mono"
            :class="
              (brrrDeal?.cash_out_routi || 0) >= 0
                ? 'text-emerald-600'
                : 'text-red-500'
            "
          >
            {{ formatMoney(brrrDeal?.cash_out_routi) }}
          </span>
        </div>
        <div class="flex flex-col text-right">
          <BreakdownTooltip
            title="Cash Flow"
            :formula="breakdownFor('cash_flow')"
            class="text-[10px] text-gray-400 uppercase justify-end"
          >
            <span>Cash Flow</span>
          </BreakdownTooltip>
          <span
            class="font-mono"
            :class="
              (brrrDeal?.cash_flow || 0) > 0
                ? 'text-emerald-600'
                : 'text-red-600'
            "
          >
            {{ formatMoney(brrrDeal?.cash_flow) }}
          </span>
        </div>
        <div class="flex flex-col">
          <span class="text-[10px] text-gray-400 uppercase">CoC</span>
          <span class="font-mono text-blue-600">{{
            brrrDeal?.cash_on_cash
              ? brrrDeal.cash_on_cash.toFixed(1) + "%"
              : "-"
          }}</span>
        </div>
        <div class="flex flex-col text-right">
          <BreakdownTooltip
            title="Equity"
            :formula="breakdownFor('equity')"
            class="text-[10px] text-gray-400 uppercase justify-end"
          >
            <span>Equity</span>
          </BreakdownTooltip>
          <span class="font-mono text-emerald-600">{{
            formatMoney(brrrDeal?.equity)
          }}</span>
        </div>
      </template>

      <template v-else>
        <!-- Flip Metrics -->
        <div class="flex flex-col text-right">
          <BreakdownTooltip
            title="Net Profit"
            :formula="breakdownFor('net_profit')"
            class="text-[10px] text-gray-400 uppercase justify-end"
          >
            <span>Net Profit</span>
          </BreakdownTooltip>
          <span
            class="font-mono font-bold"
            :class="
              (flipDeal?.net_profit || 0) > 0
                ? 'text-emerald-600'
                : 'text-red-600'
            "
          >
            {{ formatMoney(flipDeal?.net_profit) }}
          </span>
        </div>
        <div class="flex flex-col">
          <BreakdownTooltip
            title="ROI"
            :formula="breakdownFor('roi')"
            class="text-[10px] text-gray-400 uppercase"
          >
            <span>ROI</span>
          </BreakdownTooltip>
          <span class="font-mono font-semibold text-blue-600">
            {{ flipDeal?.roi ? flipDeal.roi.toFixed(1) + "%" : "-" }}
          </span>
        </div>
        <div class="flex flex-col text-right">
          <span class="text-[10px] text-gray-400 uppercase">Ann. ROI</span>
          <span class="font-mono text-purple-600">
            {{
              flipDeal?.annualized_roi
                ? flipDeal.annualized_roi.toFixed(1) + "%"
                : "-"
            }}
          </span>
        </div>
      </template>
    </div>

    <!-- Footer Stats -->
    <div
      class="mt-3 pt-2 border-t border-gray-200 flex justify-between text-xs font-medium text-gray-500"
    >
      <span>{{ deal.sqft || "-" }} sqft</span>
      <span>{{ deal.bedrooms || "-" }}bd / {{ deal.bathrooms || "-" }}ba</span>
    </div>
  </div>
</template>
