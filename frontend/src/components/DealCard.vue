<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import type { ActiveDealRes, BrrrDealRes, FlipDealRes } from "../types";
import { formatDealForClipboard } from "../utils/dealUtils";

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
</script>

<template>
  <UiCard
    tone="surface"
    padding="md"
    :data-stage="deal.stage"
    :class="cardClass"
    class="group relative overflow-hidden border-line border-l-4 cursor-grab active:cursor-grabbing hover:shadow-2"
  >
    <!-- Badge -->
    <UiBadge
      :tone="isBrrr ? 'primary' : 'warning'"
      size="sm"
      class="absolute top-2 left-2 z-10 text-[10px] font-bold uppercase tracking-wide"
    >
      {{ isBrrr ? "🏠 BRRRR" : "💰 FLIP" }}
    </UiBadge>

    <!--
      One action row instead of four hand-placed `right-*` offsets. The children
      keep their document order (delete, duplicate, move, copy) so the behaviour
      manifest is unchanged, and `flex-row-reverse` puts them on screen in the
      order the absolute offsets used to: copy, move, duplicate, delete.
    -->
    <div
      data-part="card-actions"
      class="absolute top-2 right-2 z-10 flex flex-row-reverse items-center gap-2 opacity-0 transition-opacity duration-fast ease-standard group-hover:opacity-100 focus-within:opacity-100 touch:opacity-100"
    >
      <!-- Delete Button -->
      <UiIconButton
        data-testid="dealcard.delete"
        @click.stop="onDelete(deal.id)"
        label="Delete Deal"
        variant="danger"
        size="sm"
        title="Delete Deal"
      >
        <i class="pi pi-times text-xs" aria-hidden="true"></i>
      </UiIconButton>

      <!-- Duplicate Button -->
      <UiIconButton
        data-testid="dealcard.duplicate"
        @click.stop="onDuplicate(deal.id)"
        label="Duplicate Deal"
        variant="ghost"
        size="sm"
        title="Duplicate Deal"
      >
        <i class="pi pi-copy text-xs" aria-hidden="true"></i>
      </UiIconButton>
      <!-- Move to Bought Button (only for Brought stage) -->
      <UiIconButton
        v-if="deal.stage === 3"
        data-testid="dealcard.move-to-bought"
        @click.stop="onMoveToBought(deal.id)"
        label="Move to Bought Deals"
        variant="ghost"
        size="sm"
        title="Move to Bought Deals"
      >
        <i class="pi pi-arrow-right text-xs" aria-hidden="true"></i>
      </UiIconButton>

      <!-- Copy to AI Button -->
      <UiIconButton
        data-testid="dealcard.copy"
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
    <div class="text-center mb-3 mt-6">
      <h3 class="line-clamp-2 break-words text-sm md:text-base font-medium leading-tight text-fg">
        {{ deal.address || "No Address" }}
      </h3>
    </div>

    <!-- Task Box -->
    <div
      v-if="deal.task"
      class="bg-surface-muted rounded-ctl p-2 mb-3 text-center border border-line"
    >
      <span class="text-xs text-primary uppercase tracking-wider font-semibold"
        >Current Task</span
      >
      <p class="text-sm text-fg font-medium mt-1 line-clamp-2">
        {{ deal.task }}
      </p>
    </div>

    <!-- Key Metrics Grid -->
    <div class="grid grid-cols-2 gap-y-2 gap-x-2 text-xs text-fg-muted">
      <!-- Row 1: Purchase & Rehab -->
      <div class="flex flex-col min-w-0">
        <span class="text-[10px] text-fg-muted uppercase tracking-wide">Purchase</span>
        <span class="tabular text-fg font-medium">{{
          formatMoney(deal.purchasePrice ? deal.purchasePrice * 1000 : 0)
        }}</span>
      </div>
      <div class="flex flex-col min-w-0 text-right">
        <span class="text-[10px] text-fg-muted uppercase tracking-wide">Rehab</span>
        <span class="tabular text-fg font-medium">{{
          formatMoney(deal.rehabCost ? deal.rehabCost * 1000 : 0)
        }}</span>
      </div>

      <!-- Row 2: Cash Needed (with and without buffer) -->
      <div class="flex flex-col min-w-0">
        <span class="text-[10px] text-fg-muted uppercase tracking-wide">Cash Needed</span>
        <span class="tabular text-warning font-medium">{{
          formatMoney(
            isBrrr
              ? brrrDeal?.total_cash_needed_for_deal
              : flipDeal?.total_cash_needed,
          )
        }}</span>
        <span class="text-[9px] text-fg-muted uppercase tracking-wide mt-1">w/ Buffer</span>
        <span class="tabular text-warning text-[11px]">{{
          formatMoney(
            isBrrr
              ? brrrDeal?.total_cash_needed_for_deal_with_buffer
              : flipDeal?.total_cash_needed_with_buffer,
          )
        }}</span>
      </div>

      <!-- Type Specific Rows -->
      <template v-if="isBrrr">
        <div class="flex flex-col min-w-0 text-right">
          <span class="text-[10px] text-fg-muted uppercase tracking-wide">Cash Out</span>
          <span
            class="tabular font-semibold"
            :class="
              (brrrDeal?.cash_out || 0) >= 0
                ? 'text-positive'
                : 'text-negative'
            "
          >
            {{ formatMoney(brrrDeal?.cash_out) }}
          </span>
        </div>
        <div class="flex flex-col min-w-0">
          <span class="text-[10px] text-fg-muted uppercase tracking-wide"
            >Cash Out Routi</span
          >
          <span
            class="tabular font-medium"
            :class="
              (brrrDeal?.cash_out_routi || 0) >= 0
                ? 'text-positive'
                : 'text-negative'
            "
          >
            {{ formatMoney(brrrDeal?.cash_out_routi) }}
          </span>
        </div>
        <div class="flex flex-col min-w-0 text-right">
          <span class="text-[10px] text-fg-muted uppercase tracking-wide">Cash Flow</span>
          <span
            class="tabular font-medium"
            :class="
              (brrrDeal?.cash_flow || 0) > 0
                ? 'text-positive'
                : 'text-negative'
            "
          >
            {{ formatMoney(brrrDeal?.cash_flow) }}
          </span>
        </div>
        <div class="flex flex-col min-w-0">
          <span class="text-[10px] text-fg-muted uppercase tracking-wide">CoC</span>
          <span class="tabular text-primary font-medium">{{
            brrrDeal?.cash_on_cash
              ? brrrDeal.cash_on_cash.toFixed(1) + "%"
              : "-"
          }}</span>
        </div>
        <div class="flex flex-col min-w-0 text-right">
          <span class="text-[10px] text-fg-muted uppercase tracking-wide">Equity</span>
          <span class="tabular text-positive font-medium">{{
            formatMoney(brrrDeal?.equity)
          }}</span>
        </div>
      </template>

      <template v-else>
        <!-- Flip Metrics -->
        <div class="flex flex-col min-w-0 text-right">
          <span class="text-[10px] text-fg-muted uppercase tracking-wide">Net Profit</span>
          <span
            class="tabular font-bold"
            :class="
              (flipDeal?.net_profit || 0) > 0
                ? 'text-positive'
                : 'text-negative'
            "
          >
            {{ formatMoney(flipDeal?.net_profit) }}
          </span>
        </div>
        <div class="flex flex-col min-w-0">
          <span class="text-[10px] text-fg-muted uppercase tracking-wide">ROI</span>
          <span class="tabular font-semibold text-primary">
            {{ flipDeal?.roi ? flipDeal.roi.toFixed(1) + "%" : "-" }}
          </span>
        </div>
        <div class="flex flex-col min-w-0 text-right">
          <span class="text-[10px] text-fg-muted uppercase tracking-wide">Ann. ROI</span>
          <span class="tabular text-fg font-medium">
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
      class="mt-3 pt-2 border-t border-line flex justify-between text-xs font-medium text-fg-muted tabular"
    >
      <span>{{ deal.sqft || "-" }} sqft</span>
      <span>{{ deal.bedrooms || "-" }}bd / {{ deal.bathrooms || "-" }}ba</span>
    </div>
  </UiCard>
</template>

<style scoped>
/*
 * The stage accent. It cannot be a utility class: `cardClass` reaches `UiCard`
 * as one string and `cn()` drops `border-l-blue-500` the moment the same string
 * also sets `border` and `border-gray-100`. Keying the colour off `data-stage`
 * keeps the five stages apart, on tokens, whatever the class list merges to.
 *
 * The same merge is what puts the *card* border on a token. G3 freezes
 * `stageColors`, so the baseline's `border-gray-100` stays in the script; the
 * root's static `class` carries `border-line`, Vue normalises `:class` ahead of
 * `class`, and tailwind-merge keeps the later of two border colours. Swapping
 * the order of those two attributes would quietly restore the grey, so
 * `DealCard.contract.test.ts` asserts the resolved class list on all five
 * stages.
 */
/* The frozen `cardClass` falls back to the stage-1 entry for an unknown stage; so does this. */
[data-stage] {
  border-left-color: rgb(var(--color-chart-1));
}
[data-stage="2"] {
  border-left-color: rgb(var(--color-chart-3));
}
[data-stage="3"] {
  border-left-color: rgb(var(--color-chart-2));
}
[data-stage="4"] {
  border-left-color: rgb(var(--color-chart-6));
}
[data-stage="5"] {
  border-left-color: rgb(var(--color-fg-muted) / 0.4);
}
</style>
