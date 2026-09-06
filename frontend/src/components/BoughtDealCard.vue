<script setup lang="ts">
/**
 * A bought deal on the board: a *progress* card. The question after purchase
 * is "where is this deal in its pipeline, and what is left to do", so the top
 * is a rail of every stage in the live template with the current step named,
 * a ring for the current stage's ticks, and the checklist is every stage of
 * the template as a stacked accordion — the current stage open, any other
 * one a click away, and every box tickable whatever stage it belongs to. The
 * flat `completedSubstages` map already accepts any substage id, so a task in
 * a later stage can be ticked ahead of time (UI v3, item 7).
 *
 * The card lives inside a `VueDraggable`, so nothing in here tweens: the hover
 * lift is CSS, the accordion is a `grid-template-rows` transition.
 */
import { computed, ref, watch } from "vue";
import type { BoughtDealRes, BoughtBrrrDealRes, BoughtFlipDealRes } from "../types";
import { formatDealForClipboard } from "../utils/dealUtils";
import { useBoughtDealStore } from "../stores/boughtDealStore";
import { usePipelineTemplateStore } from "../stores/pipelineTemplateStore";
import {
  resolveStage,
  getSubStagesForStage,
  canAdvance,
  getStageIndex,
  isTerminalStage,
  type BoughtDealStage,
} from "../config/boughtDealStages";

const props = defineProps<{
  deal: BoughtDealRes;
}>();

const emit = defineEmits<{
  (e: "delete", id: string): void;
  /** "Advance →": the view moves the deal one stage on, keeping every tick (4.0). */
  (e: "advance", id: string): void;
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
const stages = computed(() => pipeline.value.stages);
const stageConfig = computed(() => resolveStage(pipeline.value, props.deal.boughtStage));
const subStages = computed(() => getSubStagesForStage(pipeline.value, props.deal.boughtStage));
const allSubstagesComplete = computed(() =>
  canAdvance(pipeline.value, props.deal.boughtStage, props.deal.completedSubstages),
);

/** Index of the resolved stage, so a deleted stage id clamps like `resolveStage` does. */
const currentIndex = computed(() => getStageIndex(pipeline.value, stageConfig.value.id));

const railItems = computed(() =>
  stages.value.map((stage, index) => ({
    id: stage.id,
    label: stage.name,
    state: (index < currentIndex.value ? "done" : index === currentIndex.value ? "active" : "todo") as
      | "done"
      | "active"
      | "todo",
  })),
);

const doneCount = (stage: BoughtDealStage) =>
  stage.subStages.filter((sub) => props.deal.completedSubstages[sub.id] === true).length;

const currentDone = computed(() => doneCount(stageConfig.value));
const currentTotal = computed(() => subStages.value.length);
/** The ring takes 0–1; a stage with no tasks is simply done. */
const ringValue = computed(() => (currentTotal.value === 0 ? 1 : currentDone.value / currentTotal.value));
const ringLabel = computed(() =>
  currentTotal.value === 0
    ? `${stageConfig.value.name}: no tasks`
    : `${currentDone.value} of ${currentTotal.value} tasks done in ${stageConfig.value.name}`,
);

const canAdvanceNow = computed(
  () => allSubstagesComplete.value && !isTerminalStage(pipeline.value, stageConfig.value.id),
);

/** Which stage row is open; the current stage by default, and it follows a stage move. */
const openStage = ref<string | null>(stageConfig.value.id);
watch(
  () => props.deal.boughtStage,
  () => {
    openStage.value = stageConfig.value.id;
  },
);
const toggleStage = (stageId: string) => {
  openStage.value = openStage.value === stageId ? null : stageId;
};

/**
 * The `done/total` pill: primary for the current stage and for a *future*
 * stage that already has a tick ("already started"); muted otherwise.
 */
const pillClass = (stage: BoughtDealStage, index: number) => {
  const started = index > currentIndex.value && doneCount(stage) > 0;
  return index === currentIndex.value || started
    ? "bg-primary/12 text-primary"
    : "bg-surface-3 text-fg-muted";
};

const cardClass = computed(() => {
  let base = "bg-surface border-ui";
  if (isFlip.value) base += " bg-warning/5";
  if (allSubstagesComplete.value && subStages.value.length > 0) base += " ring-2 ring-positive/50";
  return base;
});

const formatMoney = (val?: number) => val ? `$${Math.round(val).toLocaleString()}` : "-";

/** BRRRR: what the refinance should return — ARV × LTV. `-` until both are known. */
const refiTarget = computed(() => {
  const arv = brrrDeal.value?.arv_in_thousands;
  const ltv = brrrDeal.value?.ltv_as_precent;
  return arv && ltv ? (arv * 1000 * ltv) / 100 : undefined;
});
/** FLIP: the sale price the plan is built on. */
const saleTarget = computed(() =>
  flipDeal.value?.salePrice ? flipDeal.value.salePrice * 1000 : undefined,
);

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
    :class="[cardClass, 'border-line']"
    class="group relative overflow-hidden cursor-grab active:cursor-grabbing transition-[box-shadow,transform] duration-fast ease-standard hover:shadow-2 hover:-translate-y-px"
  >
    <!-- Badge -->
    <UiBadge
      :deal-type="isBrrr ? 'BRRRR' : 'FLIP'"
      size="sm"
      class="absolute top-2 left-2 z-10 text-[10px] font-bold uppercase tracking-wide"
    >
      {{ isBrrr ? "BRRRR" : "FLIP" }}
    </UiBadge>

    <!--
      One action row instead of two hand-placed `right-*` offsets; the children
      keep their document order (delete, copy) and `flex-row-reverse` puts them
      on screen in the order the absolute offsets used to: copy, delete.
    -->
    <div
      data-part="card-actions"
      class="absolute top-2 right-2 z-10 flex flex-row-reverse items-center gap-2 opacity-0 transition-opacity duration-fast ease-standard group-hover:opacity-100 focus-within:opacity-100 touch:opacity-100"
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

    <!--
      The header block carries the board's card hook. Its centre is inert (rail,
      step line, address), so a click there bubbles to the board's open handler;
      the stage rows and checkboxes below stop propagation on purpose.
    -->
    <div data-part="header" :data-testid="`boughtdeals.card.${deal.id}`">
    <!-- Rail: every stage of the live template, the current one ringed -->
    <UiTimelineRail compact :items="railItems" class="mt-6" />

    <!-- Step line + ring for the current stage's ticks -->
    <div class="mt-2 flex items-center justify-between gap-3">
      <div class="min-w-0">
        <p class="text-xs text-fg-muted">
          Step {{ currentIndex + 1 }} of {{ stages.length }} ·
          <span class="font-semibold text-fg">{{ stageConfig.name }}</span>
        </p>
        <p v-if="deal.task" class="mt-0.5 line-clamp-1 text-xs text-fg" :title="deal.task">
          <span class="uppercase tracking-wider text-[10px] text-primary font-semibold">Task</span>
          {{ deal.task }}
        </p>
      </div>
      <UiProgressRing :value="ringValue" :size="40" :thickness="4" :label="ringLabel" class="shrink-0" />
    </div>

    <!-- Header: Address -->
    <h3 class="mt-2 line-clamp-2 break-words font-display text-sm font-semibold leading-tight tracking-display text-fg md:text-base">
      {{ deal.address || "No Address" }}
    </h3>
    </div>

    <!-- Checklist: every stage, stacked; the open row's body is the substage boxes -->
    <div data-part="stages" class="mt-3 border-t border-line pt-1">
      <div
        v-for="(stage, index) in stages"
        :key="stage.id"
        :data-state="index < currentIndex ? 'done' : index === currentIndex ? 'active' : 'todo'"
        class="border-b border-line/60 last:border-b-0"
      >
        <button
          type="button"
          :data-testid="`boughtcard.stage.${stage.id}`"
          :aria-expanded="stage.subStages.length > 0 ? openStage === stage.id : undefined"
          @click.stop="toggleStage(stage.id)"
          class="flex w-full min-h-7 items-center gap-2 rounded-ctl py-1 text-left text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span
            class="min-w-0 flex-1 truncate"
            :class="index === currentIndex ? 'font-semibold text-fg' : 'text-fg-muted'"
          >
            {{ stage.name }}
          </span>
          <span
            class="numeric shrink-0 rounded-full px-1.5 text-[10px] font-semibold leading-4"
            :class="pillClass(stage, index)"
          >
            {{ stage.subStages.length > 0 ? `${doneCount(stage)}/${stage.subStages.length}` : "—" }}
          </span>
          <i
            class="pi pi-chevron-down w-3 text-center text-[10px] text-fg-muted transition-transform duration-base ease-standard"
            :class="{ '-rotate-180': openStage === stage.id, invisible: stage.subStages.length === 0 }"
            aria-hidden="true"
          ></i>
        </button>

        <!-- CSS-only collapse: the row's grid track goes 0fr → 1fr. -->
        <div
          v-if="stage.subStages.length > 0"
          class="grid transition-[grid-template-rows] duration-base ease-standard"
          :class="openStage === stage.id ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'"
        >
          <div class="min-h-0 overflow-hidden" :inert="openStage !== stage.id">
            <div class="px-0.5 pb-2">
              <div
                v-for="sub in stage.subStages"
                :key="sub.id"
                :data-testid="`boughtcard.substage.${sub.id}`"
                class="flex items-center gap-2 py-0.5"
              >
                <input
                  type="checkbox"
                  :data-testid="`boughtcard.substage.${sub.id}.input`"
                  :aria-label="sub.label"
                  :checked="deal.completedSubstages[sub.id] === true"
                  @click.stop="onToggleSubstage(sub.id)"
                  class="h-4 w-4 shrink-0 rounded accent-primary cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                />
                <span class="text-xs text-fg-muted" :class="{ 'line-through': deal.completedSubstages[sub.id] }">
                  {{ sub.label }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Advance: the view moves the deal (4.0), keeping every tick -->
    <UiButton
      v-if="canAdvanceNow"
      data-testid="boughtcard.advance"
      size="sm"
      block
      class="mt-2"
      @click.stop="emit('advance', deal.id)"
    >
      Advance →
    </UiButton>

    <!-- Post-purchase metrics -->
    <div data-part="metrics" class="numeric mt-3 grid grid-cols-2 gap-x-2 gap-y-2 border-t border-line pt-2 text-xs text-fg-muted">
      <div class="flex flex-col min-w-0">
        <span class="text-[10px] text-fg-muted uppercase tracking-wide">Purchase</span>
        <span class="text-fg font-medium">{{ formatMoney(deal.purchasePrice ? deal.purchasePrice * 1000 : 0) }}</span>
      </div>
      <div class="flex flex-col min-w-0 text-right">
        <span class="text-[10px] text-fg-muted uppercase tracking-wide">Rehab</span>
        <span class="text-fg font-medium">{{ formatMoney(deal.rehabCost ? deal.rehabCost * 1000 : 0) }}</span>
      </div>
      <div class="flex flex-col min-w-0">
        <span class="text-[10px] text-fg-muted uppercase tracking-wide">Cash in</span>
        <span class="text-warning font-medium">{{
          formatMoney(isBrrr ? brrrDeal?.total_cash_needed_for_deal : flipDeal?.total_cash_needed)
        }}</span>
      </div>
      <div class="flex flex-col min-w-0 text-right">
        <span class="text-[10px] text-fg-muted uppercase tracking-wide">{{ isBrrr ? "Refi target" : "Sale target" }}</span>
        <span class="text-positive font-medium">{{ formatMoney(isBrrr ? refiTarget : saleTarget) }}</span>
      </div>
    </div>

    <!-- Footer Stats -->
    <div class="mt-3 flex flex-wrap items-center justify-between gap-1 border-t border-line pt-2 numeric">
      <UiChip size="sm">{{ deal.sqft || "-" }} sqft</UiChip>
      <UiChip size="sm">{{ deal.bedrooms || "-" }}bd / {{ deal.bathrooms || "-" }}ba</UiChip>
    </div>
  </UiCard>
</template>
