<script setup lang="ts">
import { ref, watch, onMounted, computed } from "vue";
import { useBoughtDealStore } from "../stores/boughtDealStore";
import { usePipelineTemplateStore } from "../stores/pipelineTemplateStore";
import { VueDraggable } from "vue-draggable-plus";
import { useDebounceFn } from "@vueuse/core";
import { formatDealForClipboard } from "../utils/dealUtils";
import BoughtDealCard from "../components/BoughtDealCard.vue";
import PipelineTemplateEditor from "../components/PipelineTemplateEditor.vue";
import DealInputsForm from "../components/DealInputsForm.vue";
import NumberInput from "../components/ui/NumberInput.vue";
import type { BoughtDealRes, AnalyzeDealReq } from "../types";
import { ensureBrrrLegacyDefaults } from "../utils/dealUtils";
import {
  resolveStage,
  getSubStagesForStage,
  canAdvance,
  getMissingSubstages,
  isTerminalStage,
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
});

// Stage color based on position in pipeline
const getStageAccentColor = (stageId: string) => {
  const stages = currentStages.value;
  const idx = stages.findIndex((s) => s.id === stageId);
  const ratio = stages.length > 1 ? idx / (stages.length - 1) : 0;
  if (ratio < 0.25) return "border-l-blue-500";
  if (ratio < 0.5) return "border-l-cyan-500";
  if (ratio < 0.75) return "border-l-emerald-500";
  return "border-l-green-600";
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

  await store.updateBoughtDealStage(deal.id, targetStageId);
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

      await store.updateBoughtDealStage(deal.id, targetStageId);
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
const editingStageConfig = computed(() =>
  editingDeal.value
    ? resolveStage(editingPipeline.value, editingDeal.value.boughtStage)
    : null
);
const editingSubStages = computed(() =>
  editingDeal.value
    ? getSubStagesForStage(editingPipeline.value, editingDeal.value.boughtStage)
    : []
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
      editingDeal.value.boughtStage = nextStage.id;
      editingDeal.value.completedSubstages = {};
      isDirty = true;
      debouncedAutoSave();
    }
  }
};

const formatCurrency = (value: number | undefined) => {
  if (value === undefined || value === null) return "-";
  if (value === -1) return "\u221E";
  if (value === -2) return "-\u221E";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
};

const formatPercent = (value: number | undefined) => {
  if (value === undefined || value === null) return "-";
  if (value === -1) return "\u221E";
  if (value === -2) return "-\u221E";
  return `${value.toFixed(2)}%`;
};

const getCashFlowColor = (value: number | undefined) => {
  if (value === undefined || value === null) return "text-gray-900";
  if (value >= 100) return "text-emerald-600";
  if (value >= 1) return "text-gray-600";
  return "text-red-600";
};

const getPerformanceColor = (value: number | undefined) => {
  if (value === undefined || value === null) return "text-gray-900";
  if (value === -1) return "text-emerald-600";
  if (value === -2) return "text-red-600";
  if (value > 0) return "text-emerald-600";
  if (value < 0) return "text-red-600";
  return "text-gray-600";
};

const getDSCRColor = (value: number | undefined) => {
  if (value === undefined || value === null) return "text-gray-900";
  if (value >= 1.2) return "text-emerald-600";
  if (value >= 1.0) return "text-gray-600";
  return "text-red-600";
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
  <div class="h-dvh flex flex-col bg-page text-fg overflow-hidden">
    <!-- Header -->
    <header
      class="flex-none p-4 md:px-8 flex flex-wrap justify-between items-center gap-3 border-b border-line bg-surface/95 md:backdrop-blur z-20 shadow-1"
    >
      <div class="flex items-center gap-3">
        <UiIconButton
          data-testid="boughtdeals.home"
          @click="$router.push('/')"
          label="Home"
          size="md"
        >
          <i class="pi pi-home text-xl" aria-hidden="true"></i>
        </UiIconButton>
        <UiSectionHeader as="h1" class="hidden md:block">
          Bought Deals
        </UiSectionHeader>
      </div>

      <!-- Tabs -->
      <UiTabs aria-label="Deal type" class="max-w-full">
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
            class="bg-line text-fg-muted px-1.5 py-0.5 rounded-full text-[10px]"
            >{{ tab.count }}</span
          >
        </UiButton>
      </UiTabs>

      <div class="flex items-center gap-2 shrink-0 ml-auto">
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
        <UiButton
          type="button"
          data-testid="boughtdeals.my-deals"
          @click="$router.push('/my-deals')"
          variant="secondary"
          size="sm"
          class="min-h-9 touch:min-h-11 gap-2"
          title="Back to active deal pipeline"
        >
          <i class="pi pi-th-large" aria-hidden="true"></i>
          <span class="hidden sm:inline">My Deals</span>
        </UiButton>
      </div>
    </header>

    <!-- Board -->
    <div class="flex-1 min-h-0 overflow-y-auto overflow-x-hidden bg-page pb-safe-b">
      <div
        class="flex flex-col px-4 pb-4 pt-2 md:pt-4 gap-6 w-full max-w-[1920px] mx-auto"
      >
        <UiCard
          v-for="stage in currentStages"
          :key="stage.id"
          :data-testid="`boughtdeals.stage.${stage.id}`"
          tone="muted"
          padding="sm"
          :class="'w-full border-l-4 ' + getStageAccentColor(stage.id)"
        >
          <!-- Row Header -->
          <template #header>
            <UiSectionHeader as="h3">
              {{ stage.name }}
              <UiBadge
                class="ml-2 align-middle bg-surface px-2.5 font-mono text-sm font-normal text-fg-muted shadow-1 ring-1 ring-inset ring-line"
              >
                {{ columns[stage.id]?.length || 0 }}
              </UiBadge>
            </UiSectionHeader>
          </template>

          <!-- Draggable Area: SortableJS owns the DOM under VueDraggable -->
          <div>
            <VueDraggable
              v-if="columns[stage.id]"
              :data-testid="`boughtdeals.draggable.${stage.id}`"
              v-model="columns[stage.id]!"
              group="bought-deals"
              @change="(e: any) => onDrop(e, stage.id)"
              @add="(e: any) => onAdd(e, stage.id)"
              :animation="150"
              class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-4 min-h-[100px]"
              ghost-class="opacity-50"
            >
              <div
                v-for="deal in columns[stage.id]"
                :key="deal.id"
                :data-testid="`boughtdeals.card.${deal.id}`"
                @click="openDeal(deal)"
                class="h-full"
              >
                <BoughtDealCard
                  :deal="deal"
                  @delete="confirmDelete(deal)"
                  class="h-full"
                />
              </div>
            </VueDraggable>
            <UiEmptyState
              v-if="!columns[stage.id]?.length"
              class="mt-3 p-4"
            >
              No deals in this stage
            </UiEmptyState>
          </div>
        </UiCard>
      </div>
    </div>

    <!-- Detail Modal -->
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

        <div ref="modalScrollContainer" class="custom-scrollbar overflow-y-auto overscroll-contain">
          <!-- Pipeline Progress Stepper -->
          <UiCard tone="muted" class="mb-6">
            <UiSectionHeader as="h4" class="mb-3">
              Pipeline Progress
            </UiSectionHeader>
            <div class="flex items-center gap-1">
              <template
                v-for="(pStage, idx) in editingPipeline.stages"
                :key="pStage.id"
              >
                <div
                  class="flex items-center gap-1"
                  :class="idx > 0 ? 'flex-1' : ''"
                >
                  <div
                    v-if="idx > 0"
                    class="h-0.5 flex-1 rounded"
                    :class="
                      idx <= editingStageIndex ? 'bg-positive' : 'bg-line'
                    "
                  ></div>
                  <div
                    :data-testid="`boughtdeals.modal.stage-step.${pStage.id}`"
                    class="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 transition-colors duration-fast ease-standard"
                    :class="
                      idx < editingStageIndex
                        ? 'bg-positive text-primary-fg'
                        : pStage.id === editingDeal.boughtStage
                          ? 'bg-primary text-primary-fg ring-2 ring-primary/30'
                          : 'bg-line text-fg-muted'
                    "
                  >
                    <i
                      v-if="idx < editingStageIndex"
                      class="pi pi-check text-[10px]"
                      aria-hidden="true"
                    ></i>
                    <span v-else>{{ idx + 1 }}</span>
                  </div>
                </div>
              </template>
            </div>
            <UiStepper
              :count="editingPipeline.stages.length"
              compact
              class="mt-2"
            >
              <span
                v-for="(pStage, idx) in editingPipeline.stages"
                :key="pStage.id"
                role="listitem"
                :data-testid="`boughtdeals.modal.stage-label.${pStage.id}`"
                :data-step="
                  idx < editingStageIndex
                    ? 'done'
                    : pStage.id === editingDeal.boughtStage
                      ? 'active'
                      : 'todo'
                "
                :data-title="pStage.name"
                class="text-[9px] md:text-xs"
              >
                {{ pStage.name }}
              </span>
            </UiStepper>
          </UiCard>

          <!-- Sub-stage Checklist for Current Stage -->
          <UiCard
            v-if="editingSubStages.length > 0"
            tone="muted"
            class="mb-6 border-primary/20 bg-primary/5"
          >
            <UiSectionHeader as="h4" class="mb-3">
              {{ editingStageConfig?.name }} — Checklist
              <template #actions>
                <UiBadge
                  v-if="editingCanAdvance"
                  tone="positive"
                  class="font-semibold"
                >
                  <i class="pi pi-check-circle" aria-hidden="true"></i> Ready to advance
                </UiBadge>
              </template>
            </UiSectionHeader>
            <div class="space-y-1">
              <label
                v-for="sub in editingSubStages"
                :key="sub.id"
                :data-testid="`boughtdeals.modal.substage.${sub.id}`"
                class="flex items-center gap-3 cursor-pointer group -mx-2 rounded-ctl px-2 py-1.5 min-h-9 hover:bg-surface transition-colors duration-fast ease-standard"
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
                class="text-xs text-fg-muted uppercase font-bold tracking-wider mb-2 block"
                >Current Task / Status</label
              >
              <textarea
                id="boughtdeals-modal-task"
                data-testid="boughtdeals.modal.task"
                v-model="editingDeal.task"
                class="ui-textarea min-h-[168px] resize-none text-lg"
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
                <div class="flex flex-col gap-1">
                  <label for="boughtdeals-modal-stage" class="text-xs text-fg-muted font-medium"
                    >Pipeline Stage</label
                  >
                  <select
                    id="boughtdeals-modal-stage"
                    data-testid="boughtdeals.modal.stage-select"
                    v-model="editingDeal.boughtStage"
                    class="ui-select text-sm"
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
              <div class="flex flex-col gap-1">
                <label for="boughtdeals-modal-zillow" class="text-xs text-fg-muted font-medium"
                  >Zillow Link</label
                >
                <input
                  id="boughtdeals-modal-zillow"
                  data-testid="boughtdeals.modal.zillow-link"
                  v-model="editingDeal.zillow_link"
                  class="ui-input text-sm"
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
              <div class="flex flex-col gap-1">
                <label for="boughtdeals-modal-pics" class="text-xs text-fg-muted font-medium"
                  >Photos Link</label
                >
                <input
                  id="boughtdeals-modal-pics"
                  data-testid="boughtdeals.modal.pics-link"
                  v-model="editingDeal.pics_link"
                  class="ui-input text-sm"
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
              <div class="flex flex-col gap-1">
                <label for="boughtdeals-modal-design" class="text-xs text-fg-muted font-medium"
                  >Overall Design</label
                >
                <input
                  id="boughtdeals-modal-design"
                  data-testid="boughtdeals.modal.overall-design"
                  v-model="editingDeal.overall_design"
                  class="ui-input text-sm"
                  placeholder="e.g. Modern Farmhouse"
                />
              </div>
              <div class="flex flex-col gap-1">
                <label for="boughtdeals-modal-crime" class="text-xs text-fg-muted font-medium"
                  >Crime Rate</label
                >
                <input
                  id="boughtdeals-modal-crime"
                  data-testid="boughtdeals.modal.crime-rate"
                  v-model="editingDeal.crime_rate"
                  class="ui-input text-sm"
                  placeholder="e.g. Low / B-"
                />
              </div>
            </div>
            <div class="space-y-4">
              <div class="flex flex-col gap-1">
                <label for="boughtdeals-modal-contact" class="text-xs text-fg-muted font-medium"
                  >Contact Info</label
                >
                <textarea
                  id="boughtdeals-modal-contact"
                  data-testid="boughtdeals.modal.contact"
                  v-model="editingDeal.contact"
                  rows="2"
                  class="ui-textarea min-h-0 text-sm"
                  placeholder="Agent / Owner details"
                ></textarea>
              </div>
              <div class="flex flex-col gap-1">
                <label for="boughtdeals-modal-niche" class="text-xs text-fg-muted font-medium"
                  >Niche</label
                >
                <input
                  id="boughtdeals-modal-niche"
                  data-testid="boughtdeals.modal.niche"
                  v-model="editingDeal.niche"
                  class="ui-input text-sm"
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
              class="bg-surface-muted p-4 rounded-card border border-line mb-6"
            >
              <UiSectionHeader as="h4" class="mb-3">
                Analysis Results
              </UiSectionHeader>
              <div
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
                      :class="getPerformanceColor((currentAnalysis as any).cash_on_cash)"
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
                    <div data-testid="boughtdeals.modal.result.equity" class="font-bold text-positive">
                      {{ formatCurrency( (currentAnalysis as any).equity ) }}
                    </div>
                  </UiStatTile>
                  <UiStatTile tone="neutral" class="bg-surface">
                    <template #label>ROI</template>
                    <div
                      data-testid="boughtdeals.modal.result.roi"
                      class="font-bold"
                      :class="getPerformanceColor((currentAnalysis as any).roi)"
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
                    <div data-testid="boughtdeals.modal.result.total_cash_needed_for_deal" class="font-bold">
                      {{ formatCurrency( (currentAnalysis as any) .total_cash_needed_for_deal ) }}
                    </div>
                  </UiStatTile>
                  <UiStatTile tone="neutral" class="bg-surface">
                    <template #label>
                      Cash Needed (Buffered)
                    </template>
                    <div data-testid="boughtdeals.modal.result.total_cash_needed_for_deal_with_buffer" class="font-bold">
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
                      :class="getPerformanceColor((currentAnalysis as any).roi)"
                    >
                      {{ formatPercent( (currentAnalysis as any).roi ) }}
                    </div>
                  </UiStatTile>
                  <UiStatTile tone="neutral" class="bg-surface">
                    <template #label>Annualized ROI</template>
                    <div
                      data-testid="boughtdeals.modal.result.annualized_roi"
                      class="font-bold"
                      :class="getPerformanceColor((currentAnalysis as any).annualized_roi)"
                    >
                      {{ formatPercent( (currentAnalysis as any).annualized_roi ) }}
                    </div>
                  </UiStatTile>
                  <UiStatTile tone="neutral" class="bg-surface">
                    <template #label>Cash Needed</template>
                    <div data-testid="boughtdeals.modal.result.total_cash_needed" class="font-bold">
                      {{ formatCurrency( (currentAnalysis as any).total_cash_needed ) }}
                    </div>
                  </UiStatTile>
                  <UiStatTile tone="neutral" class="bg-surface">
                    <template #label>Cash Needed (Buffered)</template>
                    <div data-testid="boughtdeals.modal.result.total_cash_needed_with_buffer" class="font-bold">
                      {{ formatCurrency( (currentAnalysis as any).total_cash_needed_with_buffer ) }}
                    </div>
                  </UiStatTile>
                  <UiStatTile tone="neutral" class="bg-surface">
                    <template #label>Holding Costs</template>
                    <div data-testid="boughtdeals.modal.result.total_holding_costs" class="font-bold">
                      {{ formatCurrency( (currentAnalysis as any).total_holding_costs ) }}
                    </div>
                  </UiStatTile>
                  <UiStatTile tone="neutral" class="bg-surface">
                    <template #label>HML Interest</template>
                    <div data-testid="boughtdeals.modal.result.total_hml_interest" class="font-bold">
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
              class="text-xs text-fg-muted font-medium uppercase mb-2 block"
              >Notes</label
            >
            <textarea
              id="boughtdeals-modal-notes"
              data-testid="boughtdeals.modal.notes"
              v-model="editingDeal.notes"
              rows="4"
              class="ui-textarea p-4 text-sm"
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
                <div :data-testid="`boughtdeals.sold-comp.${index}`" v-for="(comp, index) in editingDeal.sold_comps" :key="index" class="bg-surface p-2 rounded-ctl relative group border border-line">
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
                  <div :data-testid="`boughtdeals.sale-comp.${index}`" v-for="(comp, index) in (editingDeal as any).sale_comps" :key="index" class="bg-surface p-2 rounded-ctl relative group border border-line">
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
                  <div :data-testid="`boughtdeals.rent-comp.${index}`" v-for="(comp, index) in editingDeal.rent_comps" :key="index" class="bg-surface p-2 rounded-ctl relative group border border-line">
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

    <!-- Pipeline Template Editor -->
    <PipelineTemplateEditor
      :open="showPipelineEditor"
      :initial-tab="activeTab"
      @close="showPipelineEditor = false"
      @saved="refreshColumns"
    />
  </div>
</template>
