<script setup lang="ts">
import { ref, watch, onMounted, computed, nextTick } from "vue";
import { useBoughtDealStore } from "../stores/boughtDealStore";
import { usePipelineTemplateStore } from "../stores/pipelineTemplateStore";
import { VueDraggable } from "vue-draggable-plus";
import { useDebounceFn } from "@vueuse/core";
import { formatDealForClipboard } from "../utils/dealUtils";
import BoughtDealCard from "../components/BoughtDealCard.vue";
import StageColumn from "../components/board/StageColumn.vue";
import PipelineTemplateEditor from "../components/PipelineTemplateEditor.vue";
import DealInputsForm from "../components/DealInputsForm.vue";
import NumberInput from "../components/ui/NumberInput.vue";
import type { BoughtDealRes, AnalyzeDealReq } from "../types";
import { ensureBrrrLegacyDefaults } from "../utils/dealUtils";
import {
  resolveStage,
  canAdvance,
  getMissingSubstages,
  isTerminalStage,
  type BoughtDealStage,
} from "../config/boughtDealStages";

const store = useBoughtDealStore();
const pipelineStore = usePipelineTemplateStore();

const activeTab = ref<"FLIP" | "BRRRR">("BRRRR");

const currentPipeline = computed(() => pipelineStore.pipelineFor(activeTab.value));
const currentStages = computed(() => currentPipeline.value.stages);

// Template editor modal
const showPipelineEditor = ref(false);
const openPipelineEditor = () => {
  showPipelineEditor.value = true;
};

// Local state for columns keyed by stage id (string)
const columns = ref<Record<string, BoughtDealRes[]>>({});

const refreshColumns = () => {
  const deals = store.dealsByType[activeTab.value];
  const cols: Record<string, BoughtDealRes[]> = {};
  for (const stage of currentStages.value) {
    cols[stage.id] = [];
  }
  const firstStage = currentStages.value[0];
  for (const deal of deals) {
    const stageConfig = resolveStage(currentPipeline.value, deal.boughtStage);
    const targetCol = cols[stageConfig.id];
    if (targetCol) {
      targetCol.push(deal);
    } else if (firstStage) {
      // Deleted/renamed-away stage → clamp to first stage so the card never
      // disappears from the board.
      cols[firstStage.id]?.push(deal);
    }
  }
  columns.value = cols;
};

watch(
  () => [store.boughtDeals, activeTab.value, currentStages.value],
  () => refreshColumns(),
  { deep: true }
);

onMounted(async () => {
  await Promise.all([
    store.fetchBoughtDeals(),
    pipelineStore.fetchTemplates(),
  ]);
  refreshColumns();
  await nextTick();
  centreBusiestColumn();
});

// UI v3 (4.3): the stage rail.
const railEl = ref<HTMLElement | null>(null);

/** On lg+ the rail opens on the stage holding the most deals. */
const centreBusiestColumn = () => {
  const rail = railEl.value;
  if (!rail || typeof window.matchMedia !== "function") return;
  if (!window.matchMedia("(min-width: 1024px)").matches) return;
  let best = 0;
  let bestCount = -1;
  currentStages.value.forEach((s, i) => {
    const n = columns.value[s.id]?.length || 0;
    if (n > bestCount) {
      bestCount = n;
      best = i;
    }
  });
  const column = rail.children[best] as HTMLElement | undefined;
  column?.scrollIntoView({ inline: "center", block: "nearest" });
};

/** While a card is in flight, columns more than one stage away are inert. */
const draggingFromIdx = ref<number | null>(null);
const onDragStart = (stageId: string) => {
  draggingFromIdx.value = currentStages.value.findIndex((s) => s.id === stageId);
};
const onDragEnd = () => {
  draggingFromIdx.value = null;
};
const isInertDuringDrag = (idx: number) =>
  draggingFromIdx.value !== null && Math.abs(idx - draggingFromIdx.value) > 1;

/** Stage colour by position in the pipeline: a four-step ramp, as a fill, for the flow strip and the rail nodes. */
const getStageBarColor = (stageId: string) => {
  const stages = currentStages.value;
  const idx = stages.findIndex((s) => s.id === stageId);
  const ratio = stages.length > 1 ? idx / (stages.length - 1) : 0;
  if (ratio < 0.25) return "bg-chart-4";
  if (ratio < 0.5) return "bg-chart-8";
  if (ratio < 0.75) return "bg-chart-2";
  return "bg-positive";
};

/**
 * UI v3 (4.0): a stage move keeps every tick. Every stage's checklist is on
 * the card now, so a task ticked ahead of time must survive the move that
 * reaches it — and a move back must not erase the stage just left. The store's
 * `updateBoughtDealStage` / `advanceStage` reset `completedSubstages` (and are
 * frozen), so moves go through the generic `updateBoughtDeal`: the same
 * `PUT /bought-deals/{id}` autosave sends, with the map untouched. Optimistic,
 * reverted on error, like the store action it replaces.
 */
const moveDealToStage = async (deal: BoughtDealRes, targetStageId: string) => {
  const oldStage = deal.boughtStage;
  deal.boughtStage = targetStageId;
  try {
    await store.updateBoughtDeal(deal);
  } catch (err) {
    deal.boughtStage = oldStage;
    console.error("Failed to move bought deal stage:", err);
  }
};

/** The card's "Advance →": one stage forward, only when its checklist is done. */
const advanceDeal = async (deal: BoughtDealRes) => {
  const dealType = (deal.deal_type || "BRRRR") as "FLIP" | "BRRRR";
  const pipeline = pipelineStore.pipelineFor(dealType);
  if (!canAdvance(pipeline, deal.boughtStage, deal.completedSubstages)) return;
  if (isTerminalStage(pipeline, deal.boughtStage)) return;
  const idx = pipeline.stages.findIndex((s) => s.id === deal.boughtStage);
  const next = pipeline.stages[idx + 1];
  if (!next) return;
  await moveDealToStage(deal, next.id);
  refreshColumns();
};

// Drag-and-drop
const onDrop = async (event: any, targetStageId: string) => {
  if (!event.added) return;
  const deal = event.added.element as BoughtDealRes;
  if (deal.boughtStage === targetStageId) return;

  const dealType = (deal.deal_type || "BRRRR") as "FLIP" | "BRRRR";
  const pipeline = pipelineStore.pipelineFor(dealType);
  const stages = pipeline.stages;
  const currentIdx = stages.findIndex((s) => s.id === deal.boughtStage);
  const targetIdx = stages.findIndex((s) => s.id === targetStageId);

  // Only allow ±1 stage moves
  if (Math.abs(targetIdx - currentIdx) > 1) {
    alert("You can only move deals one stage at a time.");
    refreshColumns();
    return;
  }

  // Forward move: check substages
  if (targetIdx > currentIdx) {
    if (!canAdvance(pipeline, deal.boughtStage, deal.completedSubstages)) {
      const missing = getMissingSubstages(
        pipeline,
        deal.boughtStage,
        deal.completedSubstages
      );
      alert(
        `Cannot advance: complete these sub-stages first:\n- ${missing.join("\n- ")}`
      );
      refreshColumns();
      return;
    }
  }

  await moveDealToStage(deal, targetStageId);
  refreshColumns();
};

const onAdd = async (event: any, targetStageId: string) => {
  const list = columns.value[targetStageId];
  if (list && typeof event.newIndex === "number") {
    const deal = list[event.newIndex];
    if (deal && deal.boughtStage !== targetStageId) {
      const dealType = (deal.deal_type || "BRRRR") as "FLIP" | "BRRRR";
      const pipeline = pipelineStore.pipelineFor(dealType);
      const stages = pipeline.stages;
      const currentIdx = stages.findIndex((s) => s.id === deal.boughtStage);
      const targetIdx = stages.findIndex((s) => s.id === targetStageId);

      if (Math.abs(targetIdx - currentIdx) > 1) {
        alert("You can only move deals one stage at a time.");
        refreshColumns();
        return;
      }

      if (
        targetIdx > currentIdx &&
        !canAdvance(pipeline, deal.boughtStage, deal.completedSubstages)
      ) {
        const missing = getMissingSubstages(
          pipeline,
          deal.boughtStage,
          deal.completedSubstages
        );
        alert(
          `Cannot advance: complete these sub-stages first:\n- ${missing.join("\n- ")}`
        );
        refreshColumns();
        return;
      }

      await moveDealToStage(deal, targetStageId);
      refreshColumns();
    }
  }
};

const confirmDelete = async (deal: BoughtDealRes) => {
  if (confirm(`Are you sure you want to delete ${deal.address}?`)) {
    try {
      await store.deleteBoughtDeal(deal.id, deal.deal_type || "BRRRR");
      refreshColumns();
    } catch {
      alert("Failed to delete deal");
    }
  }
};

// --- Modal ---
const showDetailModal = ref(false);
const editingDeal = ref<BoughtDealRes | null>(null);

const currentAnalysis = ref<BoughtDealRes | null>(null);
const modalScrollContainer = ref<HTMLElement | null>(null);
const analysisResultsEl = ref<HTMLElement | null>(null);

const saveStatus = ref<"idle" | "saving" | "saved" | "error">("idle");
let isDirty = false;
let isInitialLoad = true;
let settleUntilMs = 0;
const MODAL_SETTLE_MS = 250;
let savedTimeoutId: ReturnType<typeof setTimeout> | null = null;

const performSave = async () => {
  if (!editingDeal.value || !isDirty) return;
  isDirty = false;
  saveStatus.value = "saving";
  try {
    const updatedDeal = await store.updateBoughtDeal(editingDeal.value);
    if (updatedDeal) {
      currentAnalysis.value = { ...editingDeal.value, ...updatedDeal };
    }
    if (isDirty) {
      debouncedAutoSave();
    } else {
      saveStatus.value = "saved";
      if (savedTimeoutId) clearTimeout(savedTimeoutId);
      savedTimeoutId = setTimeout(() => {
        saveStatus.value = "idle";
      }, 2000);
    }
  } catch {
    isDirty = true;
    saveStatus.value = "error";
  }
};

const debouncedAutoSave = useDebounceFn(performSave, 2000);

const closeModal = async () => {
  if (isDirty && editingDeal.value) {
    await performSave();
  }
  showDetailModal.value = false;
};

const openDeal = (deal: BoughtDealRes) => {
  isInitialLoad = true;
  isDirty = false;
  saveStatus.value = "idle";
  const clone = JSON.parse(JSON.stringify(deal)) as BoughtDealRes;
  ensureBrrrLegacyDefaults(clone);
  editingDeal.value = clone;
  modalOpenStage.value = clone.boughtStage;
  currentAnalysis.value = JSON.parse(JSON.stringify(clone));
  settleUntilMs = Date.now() + MODAL_SETTLE_MS;
  showDetailModal.value = true;
};

const analyzeCurrentDeal = useDebounceFn(async () => {
  if (editingDeal.value) {
    try {
      const type = editingDeal.value.deal_type || "BRRRR";
      const payload = JSON.parse(JSON.stringify(editingDeal.value));
      const result = await store.analyze(
        payload as AnalyzeDealReq,
        type
      );
      if (result) {
        currentAnalysis.value = { ...editingDeal.value, ...result };
      }
    } catch {
      // Analysis failed silently
    }
  }
}, 500);

watch(
  editingDeal,
  () => {
    if (showDetailModal.value) {
      analyzeCurrentDeal();
      if (isInitialLoad) {
        isInitialLoad = false;
        return;
      }
      if (Date.now() < settleUntilMs) {
        return;
      }
      isDirty = true;
      debouncedAutoSave();
    }
  },
  { deep: true }
);

const deleteEditingDeal = async () => {
  if (editingDeal.value) {
    if (
      confirm(
        `Are you sure you want to delete ${editingDeal.value.address}?`
      )
    ) {
      try {
        await store.deleteBoughtDeal(
          editingDeal.value.id,
          editingDeal.value.deal_type || "BRRRR"
        );
        showDetailModal.value = false;
        refreshColumns();
      } catch {
        alert("Failed to delete deal");
      }
    }
  }
};

// Modal helpers
const editingDealType = computed(
  () =>
    ((editingDeal.value?.deal_type || "BRRRR") as "FLIP" | "BRRRR")
);
const editingPipeline = computed(() =>
  pipelineStore.pipelineFor(editingDealType.value)
);
const editingCanAdvance = computed(() =>
  editingDeal.value
    ? canAdvance(
        editingPipeline.value,
        editingDeal.value.boughtStage,
        editingDeal.value.completedSubstages,
      )
    : false
);
const editingIsTerminal = computed(() =>
  editingDeal.value
    ? isTerminalStage(editingPipeline.value, editingDeal.value.boughtStage)
    : false
);
const editingStageIndex = computed(() =>
  editingDeal.value
    ? editingPipeline.value.stages.findIndex(
        (s) => s.id === editingDeal.value!.boughtStage,
      )
    : -1,
);

// UI v3 (4.4): the modal shows every stage's checklist; the current one is open.
const modalOpenStage = ref<string | null>(null);
watch(
  () => editingDeal.value?.boughtStage,
  (stageId) => {
    modalOpenStage.value = stageId ?? null;
  },
);
const modalRailItems = computed(() =>
  editingPipeline.value.stages.map((s, i) => ({
    id: s.id,
    label: s.name,
    state: (i < editingStageIndex.value
      ? "done"
      : i === editingStageIndex.value
        ? "active"
        : "todo") as "done" | "active" | "todo",
  })),
);
const modalStageDone = (stage: BoughtDealStage) =>
  stage.subStages.filter((s) => editingDeal.value?.completedSubstages[s.id] === true).length;
/** Past: muted. Current, or a later stage already started: primary tint. */
const modalStagePillClass = (stage: BoughtDealStage, idx: number) => {
  if (idx === editingStageIndex.value) return "bg-primary/12 text-primary";
  if (idx > editingStageIndex.value && modalStageDone(stage) > 0) return "bg-primary/12 text-primary";
  return "bg-surface-3 text-fg-muted";
};

const toggleModalSubstage = (substageId: string) => {
  if (!editingDeal.value) return;
  const newCompleted = { ...editingDeal.value.completedSubstages };
  if (newCompleted[substageId]) {
    delete newCompleted[substageId];
  } else {
    newCompleted[substageId] = true;
  }
  editingDeal.value.completedSubstages = newCompleted;
};

const advanceEditingDeal = async () => {
  if (!editingDeal.value || !editingCanAdvance.value || editingIsTerminal.value)
    return;

  const pipeline = editingPipeline.value;
  const currentIdx = pipeline.stages.findIndex(
    (s) => s.id === editingDeal.value!.boughtStage
  );
  if (currentIdx < pipeline.stages.length - 1) {
    const nextStage = pipeline.stages[currentIdx + 1];
    if (nextStage) {
      // Ticks are kept (UI v3 4.0): the next stage's boxes may already be ticked.
      editingDeal.value.boughtStage = nextStage.id;
      isDirty = true;
      debouncedAutoSave();
    }
  }
};

// Currency never decodes the -1/-2 sentinels: -$1 and -$2 are real amounts.
const formatCurrency = (value: number | undefined) => {
  if (value === undefined || value === null) return "-";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
};

// The calculators encode ±∞ on cash_on_cash / roi / annualized_roi as -1 / -2.
const formatPercent = (value: number | undefined) => {
  if (value === undefined || value === null) return "-";
  if (value === -1) return "\u221E%";
  if (value === -2) return "-\u221E%";
  return `${value.toFixed(2)}%`;
};

const getCashFlowColor = (value: number | undefined) => {
  if (value === undefined || value === null) return "text-fg";
  if (value >= 100) return "text-positive";
  if (value >= 1) return "text-fg-muted";
  return "text-negative";
};

const getPerformanceColor = (value: number | undefined) => {
  if (value === undefined || value === null) return "text-fg";
  if (value > 0) return "text-positive";
  if (value < 0) return "text-negative";
  return "text-fg-muted";
};

/** Tone for a percent metric: -1 (∞) is positive, -2 (-∞) is negative. */
const getPercentColor = (value: number | undefined) => {
  if (value === -1) return "text-positive";
  if (value === -2) return "text-negative";
  return getPerformanceColor(value);
};

const getDSCRColor = (value: number | undefined) => {
  if (value === undefined || value === null) return "text-fg";
  if (value >= 1.2) return "text-positive";
  if (value >= 1.0) return "text-fg-muted";
  return "text-negative";
};

const isHeaderCopied = ref(false);

const copyToClipboard = async (deal: BoughtDealRes) => {
  try {
    const text = formatDealForClipboard(deal);
    await navigator.clipboard.writeText(text);
    isHeaderCopied.value = true;
    setTimeout(() => {
      isHeaderCopied.value = false;
    }, 2000);
  } catch (err) {
    console.error("Failed to copy to clipboard", err);
  }
};
</script>

<template>
  <!--
    UI v3: a hero header (eyebrow → title → controls, one ≤ 450 ms sequence),
    then the flow strip, then the stage rail. Not sticky: each stage column
    carries its own header. The shell owns the viewport and the page scroller.
  -->
  <div class="flex min-h-full flex-col text-fg">
    <UiTransition preset="hero" appear>
      <header class="mx-auto w-full max-w-[1920px] px-4 pt-4 md:px-6 md:pt-6">
        <div class="flex flex-wrap items-end gap-3">
          <div class="min-w-0 flex-1">
            <p data-hero="eyebrow" class="numeric text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">
              Execution
            </p>
            <UiSectionHeader
              as="h2"
              data-hero="title"
              class="[&_[data-part=title]]:font-display [&_[data-part=title]]:text-2xl [&_[data-part=title]]:tracking-display"
            >
              Bought Deals
            </UiSectionHeader>
          </div>

      <!-- Tabs -->
      <UiTabs data-hero="item" aria-label="Deal type" class="max-w-full">
        <UiButton
          v-for="tab in [
            { id: 'FLIP' as const, label: 'Flip', count: store.countByType.FLIP },
            { id: 'BRRRR' as const, label: 'BRRRR', count: store.countByType.BRRRR },
          ]"
          :key="tab.id"
          :data-testid="`boughtdeals.tab.${tab.id}`"
          @click="activeTab = tab.id"
          variant="tab"
          size="sm"
          :active="activeTab === tab.id"
          class="min-h-9 touch:min-h-11 shrink-0 px-3"
        >
          {{ tab.label }}
          <span
            class="numeric rounded-full bg-surface-3 px-1.5 py-0.5 text-[10px] text-fg-muted"
            >{{ tab.count }}</span
          >
        </UiButton>
      </UiTabs>

      <div data-hero="item" class="flex items-center gap-2 shrink-0">
        <UiButton
          type="button"
          data-testid="boughtdeals.edit-pipeline"
          @click="openPipelineEditor"
          variant="secondary"
          size="sm"
          class="min-h-9 touch:min-h-11 gap-2"
          :title="`Edit ${activeTab} pipeline stages & substages`"
        >
          <i class="pi pi-sliders-v" aria-hidden="true"></i>
          <span class="hidden sm:inline">Edit Pipeline</span>
          <UiBadge
            class="hidden md:inline-flex font-bold uppercase tracking-wide"
            :tone="activeTab === 'BRRRR' ? 'primary' : 'warning'"
          >
            {{ activeTab }}
          </UiBadge>
        </UiButton>
      </div>
        </div>

        <!--
          Flow strip: one segment per stage, width ∝ deals in it (a floor keeps
          empty stages visible). The one-glance answer to "where is everything".
          Computed from the columns already on screen; no fetch.
        -->
        <div data-hero="item" data-testid="boughtdeals.flow-strip" class="mt-4">
          <div class="flex h-2 gap-1 overflow-hidden rounded-full" aria-hidden="true">
            <div
              v-for="stage in currentStages"
              :key="stage.id"
              class="h-full rounded-full transition-[flex-grow] duration-slow ease-standard"
              :class="getStageBarColor(stage.id)"
              :style="{ flexGrow: Math.max(columns[stage.id]?.length || 0, 0.35) }"
            ></div>
          </div>
          <ol class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-fg-muted">
            <li v-for="stage in currentStages" :key="stage.id" class="flex items-center gap-1.5">
              <span class="h-2 w-2 shrink-0 rounded-full" :class="getStageBarColor(stage.id)" aria-hidden="true"></span>
              <span>{{ stage.name }}</span>
              <span v-count-up class="numeric font-semibold text-fg">{{ columns[stage.id]?.length || 0 }}</span>
            </li>
          </ol>
        </div>
      </header>
    </UiTransition>

    <!--
      Board: the stage rail. On lg+ the stages are scroll-snapped columns joined
      by the connectors their headers draw; below lg they stack, as the phones
      always did. The rail is the only thing that scrolls sideways; the shell's
      <main> still owns the page scroll. `v-reveal` on the container only:
      nothing inside a VueDraggable is ever animated (SortableJS owns that DOM).
      While a card is being dragged, columns more than one stage away go inert,
      so the ±1 rule is visible before the drop and the alert is the fallback.
    -->
    <div class="flex-1 pb-safe-b">
      <div
        ref="railEl"
        v-reveal
        data-testid="boughtdeals.rail"
        class="mx-auto flex w-full max-w-[1920px] flex-col gap-4 px-4 pb-4 pt-4 md:px-6 lg:snap-x lg:snap-mandatory lg:flex-row lg:items-start lg:overflow-x-auto lg:overscroll-x-contain lg:pb-6"
      >
        <StageColumn
          v-for="(stage, idx) in currentStages"
          :key="stage.id"
          :data-testid="`boughtdeals.stage.${stage.id}`"
          :name="stage.name"
          :count="columns[stage.id]?.length || 0"
          :index="idx + 1"
          :total="currentStages.length"
          :tone="getStageBarColor(stage.id)"
          :legend="stage.subStages.map((s) => s.label)"
          :terminal="idx === currentStages.length - 1"
          :inert="isInertDuringDrag(idx)"
          class="lg:min-h-[24rem]"
        >
          <!-- Draggable Area: SortableJS owns the DOM under VueDraggable -->
          <VueDraggable
            v-if="columns[stage.id]"
            :data-testid="`boughtdeals.draggable.${stage.id}`"
            v-model="columns[stage.id]!"
            group="bought-deals"
            @change="(e: any) => onDrop(e, stage.id)"
            @add="(e: any) => onAdd(e, stage.id)"
            @start="onDragStart(stage.id)"
            @end="onDragEnd"
            :animation="150"
            class="grid min-h-[100px] grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-1"
            ghost-class="board-ghost"
            chosen-class="board-chosen"
            drag-class="board-drag"
          >
            <!-- The `boughtdeals.card.<id>` hook lives on the card's header block (see BoughtDealCard). -->
            <div
              v-for="deal in columns[stage.id]"
              :key="deal.id"
              @click="openDeal(deal)"
              class="h-full"
            >
              <BoughtDealCard
                :deal="deal"
                @delete="confirmDelete(deal)"
                @advance="advanceDeal(deal)"
                class="h-full"
              />
            </div>
          </VueDraggable>
          <template #empty>
            <p
              v-if="!columns[stage.id]?.length"
              class="mt-2 rounded-ctl border-ui border-dashed border-line px-3 py-2.5 text-center text-xs text-fg-muted"
            >
              No deals in this stage
            </p>
          </template>
        </StageColumn>
      </div>
    </div>

    <!-- Detail Modal -->
    <!--
      `UiTransition` wraps the overlay, never the panel: the `modal` preset fades
      the fixed overlay's opacity and scales only `[data-ui="modal-panel"]` inside
      it, so the box that must cover the viewport is never transformed. The 150 ms
      leave sets `pointer-events: none` before it starts, so the second half of a
      double-click cannot reach the close handler behind it.
    -->
    <UiTransition preset="modal" appear>
      <div
        v-if="showDetailModal && editingDeal"
        data-testid="boughtdeals.modal"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-fg/40 md:backdrop-blur-sm"
        @click.self="closeModal"
      >
        <UiModalPanel size="xl" labelled-by="boughtdeals-modal-title">
          <!-- Modal Header -->
          <template #header>
            <div class="flex justify-between items-center gap-3">
              <div class="flex-1 min-w-0 mr-4">
                <div class="flex items-center gap-2 mb-1">
                  <label
                    id="boughtdeals-modal-title"
                    for="boughtdeals-modal-address"
                    class="text-xs text-fg-muted uppercase font-bold tracking-wider"
                    >Address</label
                  >
                  <UiBadge
                    class="font-bold uppercase tracking-wide"
                    :deal-type="editingDealType"
                  >
                    {{ editingDealType === "BRRRR" ? "BRRRR" : "FLIP" }}
                  </UiBadge>
                </div>
                <input
                  id="boughtdeals-modal-address"
                  data-testid="boughtdeals.modal.address"
                  v-model="editingDeal.address"
                  class="w-full bg-transparent text-xl md:text-2xl font-bold text-fg border-b border-transparent hover:border-line focus:border-primary outline-none transition-colors"
                />
              </div>
              <div class="flex items-center gap-2">
                <UiIconButton
                  data-testid="boughtdeals.modal.copy"
                  @click="copyToClipboard(editingDeal)"
                  label="Copy summary for AI"
                  :class="isHeaderCopied ? 'text-positive hover:text-positive' : ''"
                  :title="isHeaderCopied ? 'Copied!' : 'Copy Summary for AI'"
                >
                  <i
                    class="pi text-xl"
                    :class="isHeaderCopied ? 'pi-check' : 'pi-file'"
                    aria-hidden="true"
                  ></i>
                </UiIconButton>
                <UiIconButton
                  data-testid="boughtdeals.modal.close"
                  @click="closeModal"
                  label="Close"
                >
                  <i class="pi pi-times text-xl" aria-hidden="true"></i>
                </UiIconButton>
              </div>
            </div>
          </template>

          <!--
            Content wrapper, deliberately *not* a scroll container — see the
            twin comment in `MyDeals.vue`. `UiModalPanel`'s `[data-part="body"]`
            is the only scroller; a second `overflow-y-auto overscroll-contain`
            here trapped the wheel in an element that had nothing to scroll and
            blocked it from chaining to the one that did, so the modal did not
            scroll on desktop. `flow-root` preserves the block formatting
            context without making this a scroll port.
          -->
          <div ref="modalScrollContainer" class="flow-root">
            <!--
              Pipeline progress (UI v3 4.4): the rail, then EVERY stage's
              checklist — the current stage open, any other a click away — so a
              task that matters two stages ahead is visible and tickable now.
              The hooks and `toggleModalSubstage` are the same as before.
            -->
            <UiCard tone="muted" class="mb-6">
              <UiSectionHeader as="h4" class="mb-3">
                Pipeline Progress
                <template #actions>
                  <UiBadge
                    v-if="editingCanAdvance && !editingIsTerminal"
                    tone="positive"
                    class="font-semibold"
                  >
                    <i class="pi pi-check-circle" aria-hidden="true"></i> Ready to advance
                  </UiBadge>
                </template>
              </UiSectionHeader>
              <UiTimelineRail :items="modalRailItems" class="mb-4" />
              <div data-testid="boughtdeals.modal.stages" class="space-y-1.5">
                <div
                  v-for="(pStage, idx) in editingPipeline.stages"
                  :key="pStage.id"
                  class="rounded-ctl border-ui bg-surface"
                  :class="pStage.id === editingDeal.boughtStage ? 'border-primary/40' : 'border-line'"
                >
                  <button
                    type="button"
                    :data-testid="`boughtdeals.modal.stage.${pStage.id}`"
                    class="flex min-h-9 w-full items-center gap-2 px-3 py-2 text-left touch:min-h-11 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-ctl"
                    :aria-expanded="modalOpenStage === pStage.id"
                    @click="modalOpenStage = modalOpenStage === pStage.id ? null : pStage.id"
                  >
                    <span
                      class="grid h-5 w-5 shrink-0 place-items-center rounded-full text-[10px] font-bold"
                      :class="
                        idx < editingStageIndex
                          ? 'bg-positive text-primary-fg'
                          : pStage.id === editingDeal.boughtStage
                            ? 'bg-primary text-primary-fg'
                            : 'bg-line text-fg-muted'
                      "
                    >
                      <i v-if="idx < editingStageIndex" class="pi pi-check text-[9px]" aria-hidden="true"></i>
                      <span v-else class="numeric">{{ idx + 1 }}</span>
                    </span>
                    <span class="min-w-0 flex-1 truncate text-sm font-medium text-fg">{{ pStage.name }}</span>
                    <span class="numeric rounded-full px-1.5 py-0.5 text-[10px]" :class="modalStagePillClass(pStage, idx)">
                      {{ pStage.subStages.length ? `${modalStageDone(pStage)}/${pStage.subStages.length}` : "—" }}
                    </span>
                    <i
                      class="pi text-[10px] text-fg-muted"
                      :class="modalOpenStage === pStage.id ? 'pi-chevron-down' : 'pi-chevron-right'"
                      aria-hidden="true"
                    ></i>
                  </button>
                  <div
                    v-if="modalOpenStage === pStage.id && pStage.subStages.length"
                    class="space-y-1 border-t border-line px-2 pb-2 pt-1"
                  >
                    <label
                      v-for="sub in pStage.subStages"
                      :key="sub.id"
                      :data-testid="`boughtdeals.modal.substage.${sub.id}`"
                      class="flex items-center gap-3 cursor-pointer group rounded-ctl px-2 py-1.5 min-h-9 hover:bg-surface-2 transition-colors duration-fast ease-standard"
                    >
                      <input
                        type="checkbox"
                        :data-testid="`boughtdeals.modal.substage.${sub.id}.input`"
                        :checked="editingDeal.completedSubstages[sub.id] === true"
                        @change="toggleModalSubstage(sub.id)"
                        class="h-4 w-4 shrink-0 rounded border-line accent-primary"
                      />
                      <span
                        class="text-sm text-fg"
                        :class="{
                          'line-through text-fg-muted':
                            editingDeal.completedSubstages[sub.id],
                        }"
                      >
                        {{ sub.label }}
                      </span>
                    </label>
                  </div>
                </div>
              </div>
              <UiButton
                v-if="editingCanAdvance && !editingIsTerminal"
                data-testid="boughtdeals.modal.advance"
                @click="advanceEditingDeal"
                variant="primary"
                class="mt-3 w-full"
              >
                <i class="pi pi-arrow-right" aria-hidden="true"></i> Advance to Next Stage
              </UiButton>
            </UiCard>

            <!-- Top Section: Task & Basic Details -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
              <UiCard tone="muted" class="md:col-span-2">
                <label
                  for="boughtdeals-modal-task"
                  class="mb-2 block text-xs font-semibold uppercase tracking-wider text-fg-muted"
                  >Current Task / Status</label
                >
                <textarea
                  id="boughtdeals-modal-task"
                  data-testid="boughtdeals.modal.task"
                  v-model="editingDeal.task"
                  class="ui-textarea min-h-[168px] resize-none text-base"
                  placeholder="What needs to be done?"
                ></textarea>
              </UiCard>

              <div class="space-y-4">
                <div class="grid grid-cols-2 gap-4">
                  <NumberInput
                    data-testid="boughtdeals.modal.sqft"
                    :model-value="editingDeal.sqft ?? null"
                    @update:model-value="
                      (val) => (editingDeal!.sqft = val ?? undefined)
                    "
                    label="SqFt"
                  />
                  <!-- The gated path (checklist → Advance) is the primary one; this select is the override and stays visible. -->
                  <div class="flex flex-col gap-1.5">
                    <label for="boughtdeals-modal-stage" class="flex h-5 items-center text-sm font-medium leading-5 text-fg"
                      >Override stage</label
                    >
                    <select
                      id="boughtdeals-modal-stage"
                      data-testid="boughtdeals.modal.stage-select"
                      v-model="editingDeal.boughtStage"
                      class="ui-select"
                    >
                      <option
                        v-for="s in editingPipeline.stages"
                        :key="s.id"
                        :value="s.id"
                      >
                        {{ s.name }}
                      </option>
                    </select>
                  </div>
                </div>
                <div class="grid grid-cols-2 gap-4">
                  <NumberInput
                    data-testid="boughtdeals.modal.bedrooms"
                    :model-value="editingDeal.bedrooms ?? null"
                    @update:model-value="
                      (val) => (editingDeal!.bedrooms = val ?? undefined)
                    "
                    label="Beds"
                  />
                  <NumberInput
                    data-testid="boughtdeals.modal.bathrooms"
                    :model-value="editingDeal.bathrooms ?? null"
                    @update:model-value="
                      (val) => (editingDeal!.bathrooms = val ?? undefined)
                    "
                    label="Baths"
                  />
                </div>
              </div>
            </div>

            <!-- Quick Links & Additional Info -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
              <div class="space-y-4">
                <div class="flex flex-col gap-1.5">
                  <label for="boughtdeals-modal-zillow" class="flex h-5 items-center text-sm font-medium leading-5 text-fg"
                    >Zillow Link</label
                  >
                  <input
                    id="boughtdeals-modal-zillow"
                    data-testid="boughtdeals.modal.zillow-link"
                    v-model="editingDeal.zillow_link"
                    class="ui-input"
                    placeholder="https://..."
                  />
                  <a
                    v-if="editingDeal.zillow_link"
                    data-testid="boughtdeals.modal.zillow-open"
                    :href="editingDeal.zillow_link"
                    target="_blank"
                    class="text-xs text-primary hover:underline inline-flex items-center gap-1 min-h-6"
                    ><i class="pi pi-external-link" aria-hidden="true"></i> Open</a
                  >
                </div>
                <div class="flex flex-col gap-1.5">
                  <label for="boughtdeals-modal-pics" class="flex h-5 items-center text-sm font-medium leading-5 text-fg"
                    >Photos Link</label
                  >
                  <input
                    id="boughtdeals-modal-pics"
                    data-testid="boughtdeals.modal.pics-link"
                    v-model="editingDeal.pics_link"
                    class="ui-input"
                    placeholder="Google Drive / Dropbox..."
                  />
                  <a
                    v-if="editingDeal.pics_link"
                    data-testid="boughtdeals.modal.pics-open"
                    :href="editingDeal.pics_link"
                    target="_blank"
                    class="text-xs text-primary hover:underline inline-flex items-center gap-1 min-h-6"
                    ><i class="pi pi-external-link" aria-hidden="true"></i> Open</a
                  >
                </div>
              </div>
              <div class="space-y-4">
                <div class="flex flex-col gap-1.5">
                  <label for="boughtdeals-modal-design" class="flex h-5 items-center text-sm font-medium leading-5 text-fg"
                    >Overall Design</label
                  >
                  <input
                    id="boughtdeals-modal-design"
                    data-testid="boughtdeals.modal.overall-design"
                    v-model="editingDeal.overall_design"
                    class="ui-input"
                    placeholder="e.g. Modern Farmhouse"
                  />
                </div>
                <div class="flex flex-col gap-1.5">
                  <label for="boughtdeals-modal-crime" class="flex h-5 items-center text-sm font-medium leading-5 text-fg"
                    >Crime Rate</label
                  >
                  <input
                    id="boughtdeals-modal-crime"
                    data-testid="boughtdeals.modal.crime-rate"
                    v-model="editingDeal.crime_rate"
                    class="ui-input"
                    placeholder="e.g. Low / B-"
                  />
                </div>
              </div>
              <div class="space-y-4">
                <div class="flex flex-col gap-1.5">
                  <label for="boughtdeals-modal-contact" class="flex h-5 items-center text-sm font-medium leading-5 text-fg"
                    >Contact Info</label
                  >
                  <textarea
                    id="boughtdeals-modal-contact"
                    data-testid="boughtdeals.modal.contact"
                    v-model="editingDeal.contact"
                    rows="2"
                    class="ui-textarea min-h-[42px]"
                    placeholder="Agent / Owner details"
                  ></textarea>
                </div>
                <div class="flex flex-col gap-1.5">
                  <label for="boughtdeals-modal-niche" class="flex h-5 items-center text-sm font-medium leading-5 text-fg"
                    >Niche</label
                  >
                  <input
                    id="boughtdeals-modal-niche"
                    data-testid="boughtdeals.modal.niche"
                    v-model="editingDeal.niche"
                    class="ui-input"
                  />
                </div>
              </div>
            </div>

            <!-- Analyze Deal Fields -->
            <div class="border-t border-line pt-6 space-y-6">
              <DealInputsForm
                :deal="editingDeal"
                :deal-type="editingDealType"
                surface="panel"
              />

              <!-- Results Preview -->
              <div
                ref="analysisResultsEl"
                v-if="currentAnalysis"
                data-testid="boughtdeals.modal.results"
                class="bg-surface-2 p-4 rounded-card border-ui border-line mb-6"
              >
                <UiSectionHeader as="h4" class="mb-3">
                  Analysis Results
                </UiSectionHeader>
                <!--
                  The reveal goes on the tile grid, never on the panel above it:
                  that panel carries `ref="analysisResultsEl"`, which Phase 4's
                  rules put out of bounds for any transition. Unlike the MyDeals
                  twin, this view's frozen script only *declares* that ref and
                  never scrolls it, so there is no scroll here to fight — the
                  rule still holds, because the two modals are deliberately
                  identical and this is the half that would diverge silently.
                  Its children may move freely.

                  Bare, not `.stagger`, for the same reason as the board above,
                  and identical to the MyDeals modal: a stagger over the ten
                  BRRRR tiles runs 0.4 s + 9 x 0.06 s = 0.94 s, well past the
                  500 ms mark `deep-link-open` measures on the twin modal.
                -->
                <div
                  v-reveal
                  class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm"
                >
                  <template v-if="editingDealType === 'BRRRR'">
                    <UiStatTile tone="neutral" class="bg-surface">
                      <template #label>Cash Flow</template>
                      <div
                        data-testid="boughtdeals.modal.result.cash_flow"
                        class="font-bold"
                        :class="getCashFlowColor((currentAnalysis as any).cash_flow)"
                      >
                        {{ formatCurrency( (currentAnalysis as any).cash_flow ) }}
                      </div>
                    </UiStatTile>
                    <UiStatTile tone="neutral" class="bg-surface">
                      <template #label>Cash Out</template>
                      <div
                        data-testid="boughtdeals.modal.result.cash_out"
                        class="font-bold"
                        :class="getPerformanceColor((currentAnalysis as any).cash_out)"
                      >
                        {{ formatCurrency( (currentAnalysis as any).cash_out ) }}
                      </div>
                    </UiStatTile>
                    <UiStatTile tone="neutral" class="bg-surface">
                      <template #label>Cash Out Routi</template>
                      <div
                        data-testid="boughtdeals.modal.result.cash_out_routi"
                        class="font-bold"
                        :class="getPerformanceColor((currentAnalysis as any).cash_out_routi)"
                      >
                        {{ formatCurrency( (currentAnalysis as any).cash_out_routi ) }}
                      </div>
                    </UiStatTile>
                    <UiStatTile tone="neutral" class="bg-surface">
                      <template #label>CoC</template>
                      <div
                        data-testid="boughtdeals.modal.result.cash_on_cash"
                        class="font-bold"
                        :class="getPercentColor((currentAnalysis as any).cash_on_cash)"
                      >
                        {{ formatPercent( (currentAnalysis as any).cash_on_cash ) }}
                      </div>
                    </UiStatTile>
                    <UiStatTile tone="neutral" class="bg-surface">
                      <template #label>DSCR</template>
                      <div
                        data-testid="boughtdeals.modal.result.dscr"
                        class="font-bold"
                        :class="getDSCRColor((currentAnalysis as any).dscr)"
                      >
                        {{ (currentAnalysis as any).dscr?.toFixed(2) || "-" }}
                      </div>
                    </UiStatTile>
                    <UiStatTile tone="neutral" class="bg-surface">
                      <template #label>Equity</template>
                      <div v-flash data-testid="boughtdeals.modal.result.equity" class="font-bold text-positive">
                        {{ formatCurrency( (currentAnalysis as any).equity ) }}
                      </div>
                    </UiStatTile>
                    <UiStatTile tone="neutral" class="bg-surface">
                      <template #label>ROI</template>
                      <div
                        data-testid="boughtdeals.modal.result.roi"
                        class="font-bold"
                        :class="getPercentColor((currentAnalysis as any).roi)"
                      >
                        {{ formatPercent( (currentAnalysis as any).roi ) }}
                      </div>
                    </UiStatTile>
                    <UiStatTile tone="neutral" class="bg-surface">
                      <template #label>Net Profit</template>
                      <div
                        data-testid="boughtdeals.modal.result.net_profit"
                        class="font-bold"
                        :class="getPerformanceColor((currentAnalysis as any).net_profit)"
                      >
                        {{ formatCurrency( (currentAnalysis as any).net_profit ) }}
                      </div>
                    </UiStatTile>
                    <UiStatTile tone="neutral" class="bg-surface">
                      <template #label>
                        Total Cash Needed
                      </template>
                      <div v-flash data-testid="boughtdeals.modal.result.total_cash_needed_for_deal" class="font-bold">
                        {{ formatCurrency( (currentAnalysis as any) .total_cash_needed_for_deal ) }}
                      </div>
                    </UiStatTile>
                    <UiStatTile tone="neutral" class="bg-surface">
                      <template #label>
                        Cash Needed (Buffered)
                      </template>
                      <div v-flash data-testid="boughtdeals.modal.result.total_cash_needed_for_deal_with_buffer" class="font-bold">
                        {{ formatCurrency( (currentAnalysis as any) .total_cash_needed_for_deal_with_buffer ) }}
                      </div>
                    </UiStatTile>
                  </template>
                  <template v-else>
                    <UiStatTile tone="neutral" class="bg-surface">
                      <template #label>Net Profit</template>
                      <div
                        data-testid="boughtdeals.modal.result.net_profit"
                        class="font-bold"
                        :class="getPerformanceColor((currentAnalysis as any).net_profit)"
                      >
                        {{ formatCurrency( (currentAnalysis as any).net_profit ) }}
                      </div>
                    </UiStatTile>
                    <UiStatTile tone="neutral" class="bg-surface">
                      <template #label>ROI</template>
                      <div
                        data-testid="boughtdeals.modal.result.roi"
                        class="font-bold"
                        :class="getPercentColor((currentAnalysis as any).roi)"
                      >
                        {{ formatPercent( (currentAnalysis as any).roi ) }}
                      </div>
                    </UiStatTile>
                    <UiStatTile tone="neutral" class="bg-surface">
                      <template #label>Annualized ROI</template>
                      <div
                        data-testid="boughtdeals.modal.result.annualized_roi"
                        class="font-bold"
                        :class="getPercentColor((currentAnalysis as any).annualized_roi)"
                      >
                        {{ formatPercent( (currentAnalysis as any).annualized_roi ) }}
                      </div>
                    </UiStatTile>
                    <UiStatTile tone="neutral" class="bg-surface">
                      <template #label>Cash Needed</template>
                      <div v-flash data-testid="boughtdeals.modal.result.total_cash_needed" class="font-bold">
                        {{ formatCurrency( (currentAnalysis as any).total_cash_needed ) }}
                      </div>
                    </UiStatTile>
                    <UiStatTile tone="neutral" class="bg-surface">
                      <template #label>Cash Needed (Buffered)</template>
                      <div v-flash data-testid="boughtdeals.modal.result.total_cash_needed_with_buffer" class="font-bold">
                        {{ formatCurrency( (currentAnalysis as any).total_cash_needed_with_buffer ) }}
                      </div>
                    </UiStatTile>
                    <UiStatTile tone="neutral" class="bg-surface">
                      <template #label>Holding Costs</template>
                      <div v-flash data-testid="boughtdeals.modal.result.total_holding_costs" class="font-bold">
                        {{ formatCurrency( (currentAnalysis as any).total_holding_costs ) }}
                      </div>
                    </UiStatTile>
                    <UiStatTile tone="neutral" class="bg-surface">
                      <template #label>HML Interest</template>
                      <div v-flash data-testid="boughtdeals.modal.result.total_hml_interest" class="font-bold">
                        {{ formatCurrency( (currentAnalysis as any).total_hml_interest ) }}
                      </div>
                    </UiStatTile>
                  </template>
                </div>
              </div>
            </div>

            <!-- Notes -->
            <div class="mt-6">
              <label
                for="boughtdeals-modal-notes"
                class="mb-2 block text-xs font-semibold uppercase tracking-wider text-fg-muted"
                >Notes</label
              >
              <textarea
                id="boughtdeals-modal-notes"
                data-testid="boughtdeals.modal.notes"
                v-model="editingDeal.notes"
                rows="4"
                class="ui-textarea"
                placeholder="Additional notes..."
              ></textarea>
            </div>

            <!-- Comps Section -->
            <div class="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6">
              <!-- Sold Comps -->
              <UiCard tone="muted">
                <UiSectionHeader as="h4" class="mb-4">
                  Sold Comps
                  <template #actions>
                    <UiButton
                      data-testid="boughtdeals.sold-comp.add"
                      @click="editingDeal.sold_comps ? editingDeal.sold_comps.push({ url: '', arv: 0, how_long_ago: '' }) : (editingDeal.sold_comps = [{ url: '', arv: 0, how_long_ago: '' }])"
                      variant="secondary"
                      size="sm"
                      class="min-h-8 touch:min-h-11"
                    >
                      <i class="pi pi-plus" aria-hidden="true"></i> Add
                    </UiButton>
                  </template>
                </UiSectionHeader>
                <div v-if="editingDeal.sold_comps && editingDeal.sold_comps.length > 0" class="space-y-3">
                  <div :data-testid="`boughtdeals.sold-comp.${index}`" v-for="(comp, index) in editingDeal.sold_comps" :key="index" class="bg-surface p-2 rounded-ctl relative group border-ui border-line">
                    <UiIconButton :data-testid="`boughtdeals.sold-comp.${index}.delete`" @click="editingDeal.sold_comps!.splice(index, 1)" label="Remove sold comp" class="absolute -top-2 -right-2 z-10 h-7 w-7 rounded-full bg-negative text-primary-fg text-xs opacity-0 transition-opacity before:-inset-2 hover:bg-negative/90 hover:text-primary-fg group-hover:opacity-100 touch:opacity-100">x</UiIconButton>
                    <div class="flex items-center gap-2 mb-1">
                      <input :data-testid="`boughtdeals.sold-comp.${index}.url`" v-model="comp.url" placeholder="URL" class="flex-1 bg-transparent border-b border-line text-xs focus:border-primary outline-none text-fg" />
                      <a v-if="comp.url" :data-testid="`boughtdeals.sold-comp.${index}.open`" :href="comp.url" target="_blank" class="text-xs text-primary hover:underline flex-none"><i class="pi pi-external-link" aria-hidden="true"></i></a>
                    </div>
                    <div class="flex gap-2">
                      <input :data-testid="`boughtdeals.sold-comp.${index}.arv`" v-model="comp.arv" type="number" placeholder="ARV" class="w-1/2 bg-transparent border-b border-line text-xs focus:border-primary outline-none text-fg" />
                      <input :data-testid="`boughtdeals.sold-comp.${index}.age`" v-model="comp.how_long_ago" placeholder="When?" class="w-1/2 bg-transparent border-b border-line text-xs focus:border-primary outline-none text-fg" />
                    </div>
                  </div>
                </div>
                <UiEmptyState v-else class="p-4">No sold comps added</UiEmptyState>
              </UiCard>

              <!-- Rent Comps / Sale Comps -->
              <UiCard tone="muted">
                <UiSectionHeader as="h4" class="mb-4">
                  {{ editingDealType === 'FLIP' ? 'For Sale Comps' : 'Rent Comps' }}
                  <template #actions>
                    <UiButton
                      data-testid="boughtdeals.comp2.add"
                      @click="editingDealType === 'FLIP' ? ((editingDeal as any).sale_comps ? (editingDeal as any).sale_comps.push({ url: '', arv: 0, how_long_ago: '' }) : ((editingDeal as any).sale_comps = [{ url: '', arv: 0, how_long_ago: '' }])) : (editingDeal.rent_comps ? editingDeal.rent_comps.push({ url: '', rent: 0, time_on_market: '' }) : (editingDeal.rent_comps = [{ url: '', rent: 0, time_on_market: '' }]))"
                      variant="secondary"
                      size="sm"
                      class="min-h-8 touch:min-h-11"
                    >
                      <i class="pi pi-plus" aria-hidden="true"></i> Add
                    </UiButton>
                  </template>
                </UiSectionHeader>

                <!-- Flip Sale Comps -->
                <div v-if="editingDealType === 'FLIP'">
                  <div v-if="(editingDeal as any).sale_comps && (editingDeal as any).sale_comps.length > 0" class="space-y-3">
                    <div :data-testid="`boughtdeals.sale-comp.${index}`" v-for="(comp, index) in (editingDeal as any).sale_comps" :key="index" class="bg-surface p-2 rounded-ctl relative group border-ui border-line">
                      <UiIconButton :data-testid="`boughtdeals.sale-comp.${index}.delete`" @click="(editingDeal as any).sale_comps!.splice(index, 1)" label="Remove sale comp" class="absolute -top-2 -right-2 z-10 h-7 w-7 rounded-full bg-negative text-primary-fg text-xs opacity-0 transition-opacity before:-inset-2 hover:bg-negative/90 hover:text-primary-fg group-hover:opacity-100 touch:opacity-100">x</UiIconButton>
                      <div class="flex items-center gap-2 mb-1">
                        <input :data-testid="`boughtdeals.sale-comp.${index}.url`" v-model="comp.url" placeholder="URL" class="flex-1 bg-transparent border-b border-line text-xs focus:border-primary outline-none text-fg" />
                        <a v-if="comp.url" :data-testid="`boughtdeals.sale-comp.${index}.open`" :href="comp.url" target="_blank" class="text-xs text-primary hover:underline flex-none"><i class="pi pi-external-link" aria-hidden="true"></i></a>
                      </div>
                      <div class="flex gap-2">
                        <input :data-testid="`boughtdeals.sale-comp.${index}.arv`" v-model="comp.arv" type="number" placeholder="List Price" class="w-1/2 bg-transparent border-b border-line text-xs focus:border-primary outline-none text-fg" />
                        <input :data-testid="`boughtdeals.sale-comp.${index}.age`" v-model="comp.how_long_ago" placeholder="Days on Mkt" class="w-1/2 bg-transparent border-b border-line text-xs focus:border-primary outline-none text-fg" />
                      </div>
                    </div>
                  </div>
                  <UiEmptyState v-else class="p-4">No active comps added</UiEmptyState>
                </div>

                <!-- BRRRR Rent Comps -->
                <div v-else>
                  <div v-if="editingDeal.rent_comps && editingDeal.rent_comps.length > 0" class="space-y-3">
                    <div :data-testid="`boughtdeals.rent-comp.${index}`" v-for="(comp, index) in editingDeal.rent_comps" :key="index" class="bg-surface p-2 rounded-ctl relative group border-ui border-line">
                      <UiIconButton :data-testid="`boughtdeals.rent-comp.${index}.delete`" @click="editingDeal.rent_comps!.splice(index, 1)" label="Remove rent comp" class="absolute -top-2 -right-2 z-10 h-7 w-7 rounded-full bg-negative text-primary-fg text-xs opacity-0 transition-opacity before:-inset-2 hover:bg-negative/90 hover:text-primary-fg group-hover:opacity-100 touch:opacity-100">x</UiIconButton>
                      <div class="flex items-center gap-2 mb-1">
                        <input :data-testid="`boughtdeals.rent-comp.${index}.url`" v-model="comp.url" placeholder="URL" class="flex-1 bg-transparent border-b border-line text-xs focus:border-primary outline-none text-fg" />
                        <a v-if="comp.url" :data-testid="`boughtdeals.rent-comp.${index}.open`" :href="comp.url" target="_blank" class="text-xs text-primary hover:underline flex-none"><i class="pi pi-external-link" aria-hidden="true"></i></a>
                      </div>
                      <div class="flex gap-2">
                        <input :data-testid="`boughtdeals.rent-comp.${index}.rent`" v-model="comp.rent" type="number" placeholder="Rent" class="w-1/2 bg-transparent border-b border-line text-xs focus:border-primary outline-none text-fg" />
                        <input :data-testid="`boughtdeals.rent-comp.${index}.age`" v-model="comp.time_on_market" placeholder="Time on Market" class="w-1/2 bg-transparent border-b border-line text-xs focus:border-primary outline-none text-fg" />
                      </div>
                    </div>
                  </div>
                  <UiEmptyState v-else class="p-4">No rent comps added</UiEmptyState>
                </div>
              </UiCard>
            </div>
          </div>

          <!-- Footer -->
          <template #footer>
            <div
              class="flex flex-wrap gap-x-4 gap-y-2 justify-between items-center"
            >
              <div class="text-xs text-fg-muted">
                Created:
                {{
                  new Date(editingDeal.created_at).toLocaleDateString()
                }}
              </div>
              <div class="flex flex-wrap items-center gap-2">
                <UiSaveStatus
                  data-testid="boughtdeals.modal.save-status"
                  :data-state="saveStatus"
                  :status="saveStatus"
                  class="mr-1"
                >
                  <template v-if="saveStatus === 'saving'">
                    <span>Saving...</span>
                  </template>
                  <template v-else-if="saveStatus === 'saved'">
                    <span>Saved</span>
                  </template>
                  <template v-else-if="saveStatus === 'error'">
                    <span>Save failed</span>
                  </template>
                </UiSaveStatus>
                <UiButton
                  data-testid="boughtdeals.modal.delete"
                  @click="deleteEditingDeal"
                  variant="ghost"
                  size="sm"
                  class="min-h-9 touch:min-h-11 text-negative hover:bg-negative/10"
                >
                  <i class="pi pi-trash" aria-hidden="true"></i> Delete
                </UiButton>
                <UiButton
                  data-testid="boughtdeals.modal.footer-close"
                  @click="closeModal"
                  variant="ghost"
                  size="sm"
                  class="min-h-9 touch:min-h-11"
                >
                  <i class="pi pi-times" aria-hidden="true"></i> Close
                </UiButton>
              </div>
            </div>
          </template>
        </UiModalPanel>
      </div>
    </UiTransition>

    <!-- Pipeline Template Editor -->
    <PipelineTemplateEditor
      :open="showPipelineEditor"
      :initial-tab="activeTab"
      @close="showPipelineEditor = false"
      @saved="refreshColumns"
    />
  </div>
</template>
