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


/**
 * Surface per stage (tokens). The stage *accent* is not a class: it is keyed
 * off `data-stage` in the scoped style below, because `cn()` would drop a
 * `border-l-*` colour against the root's `border-line`.
 */
const stageColors = {
  1: "bg-surface", // New
  2: "bg-surface", // Working
  3: "bg-surface", // Brought
  4: "bg-surface", // Keep
  5: "bg-surface-2", // Dead
};

const cardClass = computed(() => {
  // Base stage color
  let base =
    stageColors[props.deal.stage as keyof typeof stageColors] || stageColors[1];

  // Type styling
  if (isFlip.value) {
    // Add orange tint or border style?
    // Tailwind classes can be appended
    base += " bg-warning/5"; // Subtle flip tint, from the warning token
  }
  return base;
});

const formatMoney = (val?: number) =>
  val ? `$${Math.round(val).toLocaleString()}` : "-";

/**
 * Percent formatter, sentinel-aware. The calculators encode an unbounded
 * return as -1 (+∞: no cash left in the deal) and -2 (-∞: undefined) on
 * cash_on_cash / roi / annualized_roi; decode those here and only here — a
 * currency value of -$1 must never be read as ∞. A genuine 0 is "0.0%".
 */
const formatPercent = (val?: number) => {
  if (val == null) return "-";
  if (val === -1 || val === Infinity) return "∞%";
  if (val === -2 || val === -Infinity) return "-∞%";
  if (!Number.isFinite(val)) return "-";
  return `${val.toFixed(1)}%`;
};

/**
 * The verdict. A BRRRR is judged on cash-on-cash against a 10 % target, a FLIP
 * on ROI against 20 %; the ring fills toward the target and its tone turns at
 * the target (positive) and at half of it (warning).
 */
const heroTarget = computed(() => (isBrrr.value ? 10 : 20));

const heroPercent = computed(() => {
  const value = isBrrr.value ? brrrDeal.value?.cash_on_cash : flipDeal.value?.roi;
  // -1 / -2 are the calculators' ±∞ sentinels: ∞ fills the ring (positive),
  // -∞ empties it (negative), instead of both reading as "-1%" / "-2%".
  if (value === -1) return Infinity;
  if (value === -2) return -Infinity;
  return Number.isFinite(value) ? (value as number) : 0;
});

/** 0..1 — the ring's own scale — so an over-target deal shows a full ring. */
const ringValue = computed(() =>
  Math.min(1, Math.max(0, heroPercent.value / heroTarget.value)),
);

const ringTone = computed(() =>
  heroPercent.value >= heroTarget.value
    ? "positive"
    : heroPercent.value >= heroTarget.value / 2
      ? "warning"
      : "negative",
);

const heroToneClass = computed(
  () =>
    ({
      positive: "text-positive",
      warning: "text-warning",
      negative: "text-negative",
    })[ringTone.value],
);

const heroText = computed(() =>
  isBrrr.value
    ? formatPercent(brrrDeal.value?.cash_on_cash)
    : formatMoney(flipDeal.value?.net_profit),
);

const ringLabel = computed(
  () =>
    `${formatPercent(heroPercent.value)} ${isBrrr.value ? "cash on cash" : "ROI"} ` +
    `of a ${heroTarget.value}% target`,
);

/** Cash needed, and the same figure with the buffer, per deal type. */
const cashNeeded = computed(() =>
  isBrrr.value
    ? brrrDeal.value?.total_cash_needed_for_deal
    : flipDeal.value?.total_cash_needed,
);
const cashNeededWithBuffer = computed(() =>
  isBrrr.value
    ? brrrDeal.value?.total_cash_needed_for_deal_with_buffer
    : flipDeal.value?.total_cash_needed_with_buffer,
);

/**
 * The solid share of the cash bar: needed ÷ with-buffer, 0..1. Without a
 * buffer figure there is nothing to extend into, so the needed amount fills
 * the track (and an empty deal shows an empty one).
 */
const cashNeededShare = computed(() => {
  const needed = cashNeeded.value ?? 0;
  const withBuffer = cashNeededWithBuffer.value ?? 0;
  if (!(withBuffer > 0)) return needed > 0 ? 1 : 0;
  return Math.min(1, Math.max(0, needed / withBuffer));
});
</script>

<template>
  <UiCard
    tone="surface"
    padding="md"
    :data-stage="deal.stage"
    :class="cardClass"
    class="group relative overflow-hidden border-ui border-line cursor-grab active:cursor-grabbing hover:shadow-2 hover:-translate-y-px"
  >
    <!-- The stage accent: a 3 px strip along the top, coloured by the scoped CSS below. -->
    <span
      data-part="stage-strip"
      class="absolute inset-x-0 top-0 h-[3px]"
      aria-hidden="true"
    ></span>

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

    <!-- Header: type badge on the action row's line, then the address -->
    <div data-part="header" class="mb-3">
      <UiBadge
        :deal-type="isBrrr ? 'BRRRR' : 'FLIP'"
        size="sm"
        class="text-[10px] font-bold uppercase tracking-wide"
      >
        {{ isBrrr ? "BRRRR" : "FLIP" }}
      </UiBadge>
      <h3 class="mt-2 line-clamp-2 break-words font-display text-sm font-semibold leading-tight tracking-display text-fg md:text-base">
        {{ deal.address || "No Address" }}
      </h3>
    </div>

    <!-- Hero: the one number that says whether this is a good deal -->
    <div data-part="hero" class="mb-3 flex items-center gap-3">
      <div class="min-w-0 flex-1">
        <span
          class="numeric font-display text-2xl font-semibold leading-none tracking-display"
          :class="heroToneClass"
        >{{ heroText }}</span>
        <div class="mt-1 text-[10px] uppercase tracking-wide text-fg-muted">
          {{ isBrrr ? "Cash on cash" : "Net profit" }}
        </div>
      </div>
      <UiProgressRing
        :value="ringValue"
        :label="ringLabel"
        :size="44"
        :thickness="4"
        :tone="ringTone"
        class="shrink-0"
      />
    </div>

    <!-- Cash needed: one track, the buffer hatched beyond the solid amount -->
    <div data-part="cash-bar" class="mb-3">
      <div class="flex h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
        <span
          data-part="cash-needed"
          class="h-full bg-warning"
          :style="{ width: `${cashNeededShare * 100}%` }"
        ></span>
        <span data-part="cash-buffer" class="h-full flex-1 bg-warning/35"></span>
      </div>
      <div class="numeric mt-1 flex justify-between gap-2 text-[11px] text-fg-muted">
        <span>{{ formatMoney(cashNeeded) }} needed</span>
        <span>w/ buffer {{ formatMoney(cashNeededWithBuffer) }}</span>
      </div>
    </div>

    <!-- Secondary metrics: 2×2, every value the same size on one baseline -->
    <div data-part="metrics" class="grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
      <div class="flex flex-col min-w-0">
        <span class="text-[10px] text-fg-muted uppercase tracking-wide">Purchase</span>
        <span class="numeric text-fg font-medium">{{
          formatMoney(deal.purchasePrice ? deal.purchasePrice * 1000 : 0)
        }}</span>
      </div>
      <div class="flex flex-col min-w-0 text-right">
        <span class="text-[10px] text-fg-muted uppercase tracking-wide">Rehab</span>
        <span class="numeric text-fg font-medium">{{
          formatMoney(deal.rehabCost ? deal.rehabCost * 1000 : 0)
        }}</span>
      </div>

      <template v-if="isBrrr">
        <div class="flex flex-col min-w-0">
          <span class="text-[10px] text-fg-muted uppercase tracking-wide">Cash Flow</span>
          <span
            class="numeric font-medium"
            :class="
              (brrrDeal?.cash_flow || 0) > 0
                ? 'text-positive'
                : 'text-negative'
            "
          >
            {{ formatMoney(brrrDeal?.cash_flow) }}
          </span>
        </div>
        <div class="flex flex-col min-w-0 text-right">
          <span class="text-[10px] text-fg-muted uppercase tracking-wide">Equity</span>
          <span class="numeric text-fg font-medium">{{
            formatMoney(brrrDeal?.equity)
          }}</span>
        </div>
      </template>

      <template v-else>
        <div class="flex flex-col min-w-0">
          <span class="text-[10px] text-fg-muted uppercase tracking-wide">ROI</span>
          <span class="numeric text-fg font-medium">
            {{ formatPercent(flipDeal?.roi) }}
          </span>
        </div>
        <div class="flex flex-col min-w-0 text-right">
          <span class="text-[10px] text-fg-muted uppercase tracking-wide">Ann. ROI</span>
          <span class="numeric text-fg font-medium">
            {{ formatPercent(flipDeal?.annualized_roi) }}
          </span>
        </div>
      </template>
    </div>

    <!-- Next action -->
    <div
      v-if="deal.task"
      data-part="task"
      class="mt-3 flex items-center gap-2 rounded-ctl bg-surface-2 px-2 py-1.5 text-xs text-fg"
    >
      <i class="pi pi-flag text-[11px] text-primary" aria-hidden="true"></i>
      <span class="min-w-0 flex-1 truncate font-medium">{{ deal.task }}</span>
    </div>

    <!-- Footer Stats -->
    <div
      data-part="footer"
      class="mt-3 flex flex-wrap items-center gap-1.5 border-t border-line pt-2"
    >
      <UiChip size="sm" class="numeric">{{ deal.sqft || "-" }} sqft</UiChip>
      <UiChip size="sm" class="numeric">{{ deal.bedrooms || "-" }}bd / {{ deal.bathrooms || "-" }}ba</UiChip>
    </div>
  </UiCard>
</template>

<style scoped>
/*
 * The stage accent. It cannot be a utility class: `cardClass` reaches `UiCard`
 * as one string and `cn()` would drop a stage colour the moment the same
 * string also carries the root's own colours. Keying the colour off
 * `data-stage` keeps the five stages apart, on tokens, whatever the class list
 * merges to; the strip element under the root is what wears it.
 *
 * The same merge is what puts the *card* border on a token: the root's static
 * `class` carries `border-line`, Vue normalises `:class` ahead of `class`, and
 * tailwind-merge keeps the later of two border colours. Swapping the order of
 * those two attributes would quietly restore a grey, so
 * `DealCard.contract.test.ts` asserts the resolved class list on all five
 * stages.
 */
/* The frozen `cardClass` falls back to the stage-1 entry for an unknown stage; so does this. */
[data-stage] {
  --stage-accent: rgb(var(--color-chart-1));
}
[data-stage="2"] {
  --stage-accent: rgb(var(--color-chart-3));
}
[data-stage="3"] {
  --stage-accent: rgb(var(--color-chart-2));
}
[data-stage="4"] {
  --stage-accent: rgb(var(--color-chart-6));
}
[data-stage="5"] {
  --stage-accent: rgb(var(--color-fg-muted) / 0.4);
}
[data-part="stage-strip"] {
  background-image: linear-gradient(
    90deg,
    var(--stage-accent) 0%,
    var(--stage-accent) 55%,
    transparent 100%
  );
}
/* The buffer: the warning wash, hatched so it reads as "beyond the amount". */
[data-part="cash-buffer"] {
  background-image: repeating-linear-gradient(
    135deg,
    transparent 0 3px,
    rgb(var(--color-warning) / 0.35) 3px 5px
  );
}
</style>
