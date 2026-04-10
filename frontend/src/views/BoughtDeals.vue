<script setup lang="ts">
import { ref, watch, onMounted, computed } from "vue";
import { useBoughtDealStore } from "../stores/boughtDealStore";
import { VueDraggable } from "vue-draggable-plus";
import { useDebounceFn } from "@vueuse/core";
import { formatDealForClipboard } from "../utils/dealUtils";
import BoughtDealCard from "../components/BoughtDealCard.vue";
import NumberInput from "../components/ui/NumberInput.vue";
import MoneyInput from "../components/ui/MoneyInput.vue";
import SliderField from "../components/ui/SliderField.vue";
import ToggleSwitch from "primevue/toggleswitch";
import type { BoughtDealRes, AnalyzeDealReq } from "../types";
import {
  getPipelineForType,
  getStageConfig,
  getSubStagesForStage,
  canAdvance,
  getMissingSubstages,
  isTerminalStage,
} from "../config/boughtDealStages";

const store = useBoughtDealStore();

const activeTab = ref<"FLIP" | "BRRRR">("BRRRR");

const currentPipeline = computed(() => getPipelineForType(activeTab.value));
const currentStages = computed(() => currentPipeline.value.stages);

// Local state for columns keyed by stage id
const columns = ref<Record<number, BoughtDealRes[]>>({});

const refreshColumns = () => {
  const deals = store.dealsByType[activeTab.value];
  const cols: Record<number, BoughtDealRes[]> = {};
  for (const stage of currentStages.value) {
    cols[stage.id] = [];
  }
  const firstStage = currentStages.value[0];
  for (const deal of deals) {
    const stageConfig = getStageConfig(activeTab.value, deal.boughtStage);
    const targetCol = cols[stageConfig.id];
    if (targetCol) {
      targetCol.push(deal);
    } else if (firstStage) {
      cols[firstStage.id]?.push(deal);
    }
  }
  columns.value = cols;
};

watch(
  () => [store.boughtDeals, activeTab.value],
  () => refreshColumns(),
  { deep: true }
);

onMounted(async () => {
  await store.fetchBoughtDeals();
  refreshColumns();
});

// Stage color based on position in pipeline
const getStageAccentColor = (stageId: number) => {
  const stages = currentStages.value;
  const idx = stages.findIndex((s) => s.id === stageId);
  const ratio = stages.length > 1 ? idx / (stages.length - 1) : 0;
  if (ratio < 0.25) return "border-l-blue-500";
  if (ratio < 0.5) return "border-l-cyan-500";
  if (ratio < 0.75) return "border-l-emerald-500";
  return "border-l-green-600";
};

// Drag-and-drop
const onDrop = async (event: any, targetStageId: number) => {
  if (!event.added) return;
  const deal = event.added.element as BoughtDealRes;
  if (deal.boughtStage === targetStageId) return;

  const dealType = (deal.deal_type || "BRRRR") as "FLIP" | "BRRRR";
  const stages = getPipelineForType(dealType).stages;
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
    if (!canAdvance(dealType, deal.boughtStage, deal.completedSubstages)) {
      const missing = getMissingSubstages(
        dealType,
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

  // Apply stage change
  await store.updateBoughtDealStage(deal.id, targetStageId);
  refreshColumns();
};

const onAdd = async (event: any, targetStageId: number) => {
  const list = columns.value[targetStageId];
  if (list && typeof event.newIndex === "number") {
    const deal = list[event.newIndex];
    if (deal && deal.boughtStage !== targetStageId) {
      // Same validation as onDrop
      const dealType = (deal.deal_type || "BRRRR") as "FLIP" | "BRRRR";
      const stages = getPipelineForType(dealType).stages;
      const currentIdx = stages.findIndex((s) => s.id === deal.boughtStage);
      const targetIdx = stages.findIndex((s) => s.id === targetStageId);

      if (Math.abs(targetIdx - currentIdx) > 1) {
        alert("You can only move deals one stage at a time.");
        refreshColumns();
        return;
      }

      if (
        targetIdx > currentIdx &&
        !canAdvance(dealType, deal.boughtStage, deal.completedSubstages)
      ) {
        const missing = getMissingSubstages(
          dealType,
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
  editingDeal.value = JSON.parse(JSON.stringify(deal));
  currentAnalysis.value = JSON.parse(JSON.stringify(deal));
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
const editingStageConfig = computed(() =>
  editingDeal.value
    ? getStageConfig(editingDealType.value, editingDeal.value.boughtStage)
    : null
);
const editingSubStages = computed(() =>
  editingDeal.value
    ? getSubStagesForStage(
        editingDealType.value,
        editingDeal.value.boughtStage
      )
    : []
);
const editingCanAdvance = computed(() =>
  editingDeal.value
    ? canAdvance(
        editingDealType.value,
        editingDeal.value.boughtStage,
        editingDeal.value.completedSubstages
      )
    : false
);
const editingIsTerminal = computed(() =>
  editingDeal.value
    ? isTerminalStage(editingDealType.value, editingDeal.value.boughtStage)
    : false
);
const editingPipeline = computed(() =>
  getPipelineForType(editingDealType.value)
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

const quickCalcSellingCosts = () => {
  if (editingDeal.value) {
    (editingDeal.value as any).buyerAgentSellingFee = 3;
    (editingDeal.value as any).sellerAgentSellingFee = 3;
    (editingDeal.value as any).sellingClosingCosts = 5;
  }
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
  <div
    class="h-screen flex flex-col bg-gray-50 text-gray-900 overflow-hidden"
  >
    <!-- Header -->
    <header
      class="flex-none p-4 md:px-8 flex justify-between items-center border-b border-gray-200 bg-white/95 backdrop-blur z-20 shadow-sm"
    >
      <div class="flex items-center gap-4">
        <button
          @click="$router.push('/')"
          class="text-gray-500 hover:text-blue-600 transition-colors"
        >
          <i class="pi pi-home text-xl"></i>
        </button>
        <h1 class="text-2xl font-bold text-gray-900 hidden md:block">
          Bought Deals
        </h1>
      </div>

      <!-- Tabs -->
      <div class="flex bg-gray-100 rounded-lg p-1 border border-gray-200">
        <button
          v-for="tab in [
            { id: 'FLIP' as const, label: 'Flip', count: store.countByType.FLIP },
            { id: 'BRRRR' as const, label: 'BRRRR', count: store.countByType.BRRRR },
          ]"
          :key="tab.id"
          @click="activeTab = tab.id"
          class="px-3 py-1.5 text-sm font-medium rounded-md transition-all flex items-center gap-2"
          :class="
            activeTab === tab.id
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          "
        >
          {{ tab.label }}
          <span
            class="bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded-full text-[10px]"
            >{{ tab.count }}</span
          >
        </button>
      </div>

      <button
        type="button"
        @click="$router.push('/my-deals')"
        class="text-sm font-medium text-blue-700 hover:text-blue-800 border border-blue-200 bg-blue-50/80 hover:bg-blue-100 px-3 py-1.5 rounded-lg transition-colors flex items-center gap-2 shrink-0"
        title="Back to active deal pipeline"
      >
        <i class="pi pi-th-large"></i>
        <span class="hidden sm:inline">My Deals</span>
      </button>
    </header>

    <!-- Board -->
    <div class="flex-1 overflow-y-auto overflow-x-hidden bg-gray-50">
      <div
        class="flex flex-col px-4 pb-4 pt-2 md:pt-4 gap-8 w-full max-w-[1920px] mx-auto"
      >
        <div
          v-for="stage in currentStages"
          :key="stage.id"
          class="flex flex-col w-full rounded-xl border shadow-sm transition-colors bg-white border-gray-200"
        >
          <!-- Row Header -->
          <div
            class="flex-none p-4 flex justify-between items-center border-b border-gray-100 bg-gray-50/50 rounded-t-xl"
            :class="'border-l-4 ' + getStageAccentColor(stage.id)"
          >
            <div class="flex items-center gap-3">
              <h3 class="font-bold text-lg text-gray-800">
                {{ stage.name }}
              </h3>
              <span
                class="bg-white px-2.5 py-0.5 rounded-full text-sm font-mono text-gray-500 border border-gray-200 shadow-sm"
              >
                {{ columns[stage.id]?.length || 0 }}
              </span>
            </div>
          </div>

          <!-- Draggable Area -->
          <div class="p-4 bg-white/50">
            <VueDraggable
              v-if="columns[stage.id]"
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
          </div>
        </div>
      </div>
    </div>

    <!-- Detail Modal -->
    <div
      v-if="showDetailModal && editingDeal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
      @click.self="closeModal"
    >
      <div
        class="bg-white w-full max-w-6xl max-h-[95vh] rounded-2xl border border-gray-200 shadow-2xl flex flex-col"
      >
        <!-- Modal Header -->
        <div
          class="flex justify-between items-center p-6 border-b border-gray-100 shrink-0"
        >
          <div class="flex-1 mr-4">
            <div class="flex items-center gap-2 mb-1">
              <label
                class="text-xs text-gray-500 uppercase font-bold tracking-wider"
                >Address</label
              >
              <span
                class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border"
                :class="
                  editingDealType === 'BRRRR'
                    ? 'bg-blue-100 text-blue-700 border-blue-200'
                    : 'bg-orange-100 text-orange-700 border-orange-200'
                "
              >
                {{ editingDealType === "BRRRR" ? "BRRRR" : "FLIP" }}
              </span>
            </div>
            <input
              v-model="editingDeal.address"
              class="w-full bg-transparent text-2xl font-bold text-gray-900 border-b border-transparent hover:border-gray-200 focus:border-blue-500 outline-none transition-colors"
            />
          </div>
          <div class="flex items-center gap-4">
            <button
              @click="copyToClipboard(editingDeal)"
              class="transition-colors"
              :class="
                isHeaderCopied
                  ? 'text-green-600'
                  : 'text-gray-400 hover:text-purple-600'
              "
              :title="isHeaderCopied ? 'Copied!' : 'Copy Summary for AI'"
            >
              <i
                class="pi text-xl"
                :class="isHeaderCopied ? 'pi-check' : 'pi-file'"
              ></i>
            </button>
            <button
              @click="closeModal"
              class="text-gray-400 hover:text-gray-600"
            >
              <i class="pi pi-times text-xl"></i>
            </button>
          </div>
        </div>

        <div ref="modalScrollContainer" class="p-6 overflow-y-auto custom-scrollbar">
          <!-- Pipeline Progress Stepper -->
          <div class="mb-6 bg-gray-50 p-4 rounded-xl border border-gray-200">
            <h4
              class="text-xs text-gray-500 uppercase font-bold tracking-wider mb-3"
            >
              Pipeline Progress
            </h4>
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
                      pStage.id <= editingDeal.boughtStage
                        ? 'bg-emerald-400'
                        : 'bg-gray-200'
                    "
                  ></div>
                  <div
                    class="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 transition-colors"
                    :class="
                      pStage.id < editingDeal.boughtStage
                        ? 'bg-emerald-500 text-white'
                        : pStage.id === editingDeal.boughtStage
                          ? 'bg-blue-500 text-white ring-2 ring-blue-200'
                          : 'bg-gray-200 text-gray-500'
                    "
                  >
                    <i
                      v-if="pStage.id < editingDeal.boughtStage"
                      class="pi pi-check text-[10px]"
                    ></i>
                    <span v-else>{{ idx + 1 }}</span>
                  </div>
                </div>
              </template>
            </div>
            <div class="flex justify-between mt-2">
              <span
                v-for="(pStage, idx) in editingPipeline.stages"
                :key="pStage.id"
                class="text-[9px] text-gray-500 text-center"
                :class="idx === 0 ? 'text-left' : idx === editingPipeline.stages.length - 1 ? 'text-right' : ''"
                :style="{ width: 100 / editingPipeline.stages.length + '%' }"
              >
                {{ pStage.name }}
              </span>
            </div>
          </div>

          <!-- Sub-stage Checklist for Current Stage -->
          <div
            v-if="editingSubStages.length > 0"
            class="mb-6 bg-blue-50/50 p-4 rounded-xl border border-blue-100"
          >
            <div class="flex justify-between items-center mb-3">
              <h4 class="text-sm font-semibold text-gray-700">
                {{ editingStageConfig?.name }} — Checklist
              </h4>
              <span
                v-if="editingCanAdvance"
                class="text-xs text-emerald-600 font-semibold flex items-center gap-1"
              >
                <i class="pi pi-check-circle"></i> Ready to advance
              </span>
            </div>
            <div class="space-y-2">
              <label
                v-for="sub in editingSubStages"
                :key="sub.id"
                class="flex items-center gap-3 cursor-pointer group"
              >
                <input
                  type="checkbox"
                  :checked="editingDeal.completedSubstages[sub.id] === true"
                  @change="toggleModalSubstage(sub.id)"
                  class="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span
                  class="text-sm text-gray-700 group-hover:text-gray-900"
                  :class="{
                    'line-through text-gray-400':
                      editingDeal.completedSubstages[sub.id],
                  }"
                >
                  {{ sub.label }}
                </span>
              </label>
            </div>
            <button
              v-if="editingCanAdvance && !editingIsTerminal"
              @click="advanceEditingDeal"
              class="mt-3 w-full bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-lg text-sm font-bold shadow flex items-center justify-center gap-2 transition-all"
            >
              <i class="pi pi-arrow-right"></i> Advance to Next Stage
            </button>
          </div>

          <!-- Top Section: Task & Basic Details -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div
              class="md:col-span-2 bg-gray-50 p-4 rounded-xl border border-gray-200 flex flex-col justify-start min-h-[200px]"
            >
              <label
                class="text-xs text-gray-500 uppercase font-bold tracking-wider mb-2"
                >Current Task / Status</label
              >
              <textarea
                v-model="editingDeal.task"
                class="w-full h-full bg-transparent text-lg text-gray-800 resize-none outline-none placeholder-gray-400"
                placeholder="What needs to be done?"
              ></textarea>
            </div>

            <div class="space-y-4">
              <div class="grid grid-cols-2 gap-4">
                <NumberInput
                  :model-value="editingDeal.sqft ?? null"
                  @update:model-value="
                    (val) => (editingDeal!.sqft = val ?? undefined)
                  "
                  label="SqFt"
                />
                <div class="flex flex-col gap-1">
                  <label class="text-xs text-gray-600 font-medium"
                    >Pipeline Stage</label
                  >
                  <select
                    v-model="editingDeal.boughtStage"
                    class="bg-gray-50 border border-gray-200 rounded-lg px-2 py-2 text-gray-900 text-sm outline-none focus:ring-1 focus:ring-blue-500"
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
                  :model-value="editingDeal.bedrooms ?? null"
                  @update:model-value="
                    (val) => (editingDeal!.bedrooms = val ?? undefined)
                  "
                  label="Beds"
                />
                <NumberInput
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
                <label class="text-xs text-gray-600 font-medium"
                  >Zillow Link</label
                >
                <input
                  v-model="editingDeal.zillow_link"
                  class="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-gray-900 text-sm outline-none focus:border-blue-500"
                  placeholder="https://..."
                />
                <a
                  v-if="editingDeal.zillow_link"
                  :href="editingDeal.zillow_link"
                  target="_blank"
                  class="text-xs text-blue-500 hover:text-blue-700 flex items-center gap-1"
                  ><i class="pi pi-external-link"></i> Open</a
                >
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-xs text-gray-600 font-medium"
                  >Photos Link</label
                >
                <input
                  v-model="editingDeal.pics_link"
                  class="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-gray-900 text-sm outline-none focus:border-blue-500"
                  placeholder="Google Drive / Dropbox..."
                />
                <a
                  v-if="editingDeal.pics_link"
                  :href="editingDeal.pics_link"
                  target="_blank"
                  class="text-xs text-blue-500 hover:text-blue-700 flex items-center gap-1"
                  ><i class="pi pi-external-link"></i> Open</a
                >
              </div>
            </div>
            <div class="space-y-4">
              <div class="flex flex-col gap-1">
                <label class="text-xs text-gray-600 font-medium"
                  >Overall Design</label
                >
                <input
                  v-model="editingDeal.overall_design"
                  class="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-gray-900 text-sm outline-none focus:border-blue-500"
                  placeholder="e.g. Modern Farmhouse"
                />
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-xs text-gray-600 font-medium"
                  >Crime Rate</label
                >
                <input
                  v-model="editingDeal.crime_rate"
                  class="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-gray-900 text-sm outline-none focus:border-blue-500"
                  placeholder="e.g. Low / B-"
                />
              </div>
            </div>
            <div class="space-y-4">
              <div class="flex flex-col gap-1">
                <label class="text-xs text-gray-600 font-medium"
                  >Contact Info</label
                >
                <textarea
                  v-model="editingDeal.contact"
                  rows="2"
                  class="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-gray-900 text-sm outline-none focus:border-blue-500"
                  placeholder="Agent / Owner details"
                ></textarea>
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-xs text-gray-600 font-medium"
                  >Niche</label
                >
                <input
                  v-model="editingDeal.niche"
                  class="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-gray-900 text-sm outline-none focus:border-blue-500"
                />
              </div>
            </div>
          </div>

          <!-- Analyze Deal Fields -->
          <div class="border-t border-gray-200 pt-6 space-y-6">
            <!-- Buy & Rehab -->
            <section
              class="bg-gray-50 p-6 rounded-2xl border border-gray-200 shadow-sm"
            >
              <h2
                class="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2"
              >
                <i class="pi pi-home text-blue-500"></i> Buy & Rehab
              </h2>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <MoneyInput
                  :model-value="editingDeal.purchasePrice ?? null"
                  @update:model-value="
                    (v: number | null) =>
                      (editingDeal!.purchasePrice = v ?? undefined)
                  "
                  label="Purchase Price"
                  :inThousands="true"
                  :required="true"
                />
                <div class="grid grid-cols-2 gap-2">
                  <MoneyInput
                    :model-value="editingDeal.rehabCost ?? null"
                    @update:model-value="
                      (v: number | null) =>
                        (editingDeal!.rehabCost = v ?? undefined)
                    "
                    label="Rehab Cost"
                    :inThousands="true"
                  />
                  <NumberInput
                    :model-value="editingDeal.rehabContingency ?? null"
                    @update:model-value="
                      (v: number | null) =>
                        (editingDeal!.rehabContingency = v ?? undefined)
                    "
                    label="Contingency"
                    suffix="%"
                    :min="0"
                    :max="100"
                  />
                </div>
                <MoneyInput
                  :model-value="editingDeal.closingCostsBuy ?? null"
                  @update:model-value="
                    (v: number | null) =>
                      (editingDeal!.closingCostsBuy = v ?? undefined)
                  "
                  label="Closing Costs (Buy)"
                  :inThousands="true"
                />

                <div
                  class="md:col-span-2 border-t border-gray-200 my-2 pt-4"
                >
                  <h3 class="text-sm font-semibold text-gray-600 mb-3">
                    Hard Money Details
                  </h3>
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <NumberInput
                      :model-value="editingDeal.down_payment ?? null"
                      @update:model-value="
                        (v: number | null) =>
                          (editingDeal!.down_payment = v ?? undefined)
                      "
                      label="Down Payment"
                      suffix="%"
                      :min="0"
                      :max="100"
                    />
                    <NumberInput
                      :model-value="editingDeal.hmlPoints ?? null"
                      @update:model-value="
                        (v: number | null) =>
                          (editingDeal!.hmlPoints = v ?? undefined)
                      "
                      label="Points"
                      suffix=" pts"
                      :min="0"
                      :max="100"
                    />
                    <NumberInput
                      :model-value="editingDeal.HMLInterestRate ?? null"
                      @update:model-value="
                        (v: number | null) =>
                          (editingDeal!.HMLInterestRate = v ?? undefined)
                      "
                      label="Interest Rate"
                      suffix="%"
                      :min="0"
                      :max="100"
                    />
                    <div
                      class="flex items-center justify-between bg-white p-3 rounded-lg border border-gray-200"
                    >
                      <span class="text-sm font-medium text-gray-700"
                        >Use HM for Rehab</span
                      >
                      <ToggleSwitch
                        v-model="editingDeal.use_HM_for_rehab"
                        :pt="{
                          slider: ({ props }: any) => ({
                            class: props.modelValue
                              ? 'bg-blue-500'
                              : 'bg-gray-400',
                          }),
                        }"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <template v-if="editingDealType === 'BRRRR'">
              <!-- BRRRR Section -->
              <section
                class="bg-gray-50 p-6 rounded-2xl border border-gray-200 shadow-sm"
              >
                <h2
                  class="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2"
                >
                  <i class="pi pi-refresh text-blue-500"></i> Refinance
                  (BRRRR)
                </h2>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <MoneyInput
                    :model-value="
                      (editingDeal as any).arv_in_thousands ?? null
                    "
                    @update:model-value="
                      (v: number | null) =>
                        ((editingDeal as any).arv_in_thousands =
                          v ?? undefined)
                    "
                    label="ARV"
                    :inThousands="true"
                    :required="true"
                  />
                  <SliderField
                    :model-value="
                      (editingDeal as any).ltv_as_precent ?? 75
                    "
                    @update:model-value="
                      (v: number) =>
                        ((editingDeal as any).ltv_as_precent = v)
                    "
                    label="LTV"
                    :min="1"
                    :max="100"
                    suffix="%"
                    :required="true"
                  />
                  <NumberInput
                    :model-value="
                      (editingDeal as any).monthsUntilRefi ?? null
                    "
                    @update:model-value="
                      (v: number | null) =>
                        ((editingDeal as any).monthsUntilRefi =
                          v ?? undefined)
                    "
                    label="Months until Refi"
                    suffix=" mos"
                  />
                  <MoneyInput
                    :model-value="
                      (editingDeal as any).closingCostsRefi ?? null
                    "
                    @update:model-value="
                      (v: number | null) =>
                        ((editingDeal as any).closingCostsRefi =
                          v ?? undefined)
                    "
                    label="Refi Closing Costs"
                    :inThousands="true"
                  />
                  <NumberInput
                    :model-value="
                      (editingDeal as any).refiPoints ?? 1.5
                    "
                    @update:model-value="
                      (v: number | null) =>
                        ((editingDeal as any).refiPoints = v ?? 1.5)
                    "
                    label="Refi Points"
                    suffix=" pts"
                    :min="0"
                    :max="100"
                  />
                  <SliderField
                    :model-value="
                      (editingDeal as any).interestRate ?? 6.5
                    "
                    @update:model-value="
                      (v: number) =>
                        ((editingDeal as any).interestRate = v)
                    "
                    label="Long Term Interest Rate"
                    :min="0"
                    :max="20"
                    :step="0.125"
                    suffix="%"
                    :required="true"
                  />
                  <NumberInput
                    :model-value="
                      (editingDeal as any).loanTermYears ?? null
                    "
                    @update:model-value="
                      (v: number | null) =>
                        ((editingDeal as any).loanTermYears =
                          v ?? undefined)
                    "
                    label="Loan Term"
                    suffix=" Years"
                  />
                </div>
              </section>
            </template>

            <template v-else>
              <!-- FLIP Section -->
              <section
                class="bg-gray-50 p-6 rounded-2xl border border-gray-200 shadow-sm"
              >
                <h2
                  class="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2"
                >
                  <i class="pi pi-dollar text-orange-500"></i> Flip Strategy
                </h2>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <MoneyInput
                    :model-value="(editingDeal as any).salePrice ?? null"
                    @update:model-value="
                      (v: number | null) =>
                        ((editingDeal as any).salePrice = v ?? undefined)
                    "
                    label="Projected Sale Price"
                    :inThousands="true"
                    :required="true"
                  />
                  <NumberInput
                    :model-value="
                      (editingDeal as any).holdingTime ?? null
                    "
                    @update:model-value="
                      (v: number | null) =>
                        ((editingDeal as any).holdingTime =
                          v ?? undefined)
                    "
                    label="Holding Time"
                    suffix=" mos"
                    :required="true"
                  />

                  <div
                    class="md:col-span-2 bg-white rounded-lg p-3 border border-gray-200 mt-1"
                  >
                    <div
                      class="flex justify-between items-center mb-3"
                    >
                      <h3
                        class="text-sm font-semibold text-gray-700"
                      >
                        Selling Costs Breakdown
                      </h3>
                      <button
                        @click="quickCalcSellingCosts"
                        class="px-2 py-1 text-xs bg-gray-50 border border-gray-200 rounded hover:bg-gray-100 text-gray-600 transition-colors shadow-sm"
                      >
                        Quick Defaults (3%/3%/$5k)
                      </button>
                    </div>
                    <div
                      class="grid grid-cols-1 md:grid-cols-3 gap-4"
                    >
                      <NumberInput
                        :model-value="
                          (editingDeal as any).buyerAgentSellingFee ??
                          null
                        "
                        @update:model-value="
                          (v: number | null) =>
                            ((editingDeal as any).buyerAgentSellingFee =
                              v ?? undefined)
                        "
                        label="Buyer Agent Fee"
                        suffix="%"
                      />
                      <NumberInput
                        :model-value="
                          (editingDeal as any)
                            .sellerAgentSellingFee ?? null
                        "
                        @update:model-value="
                          (v: number | null) =>
                            ((editingDeal as any).sellerAgentSellingFee =
                              v ?? undefined)
                        "
                        label="Seller Agent Fee"
                        suffix="%"
                      />
                      <MoneyInput
                        :model-value="
                          (editingDeal as any).sellingClosingCosts ??
                          null
                        "
                        @update:model-value="
                          (v: number | null) =>
                            ((editingDeal as any).sellingClosingCosts =
                              v ?? undefined)
                        "
                        label="Closing Costs"
                        :inThousands="true"
                      />
                    </div>
                  </div>
                  <NumberInput
                    :model-value="
                      (editingDeal as any).capitalGainsTax ?? null
                    "
                    @update:model-value="
                      (v: number | null) =>
                        ((editingDeal as any).capitalGainsTax =
                          v ?? undefined)
                    "
                    label="Capital Gains Tax Rate"
                    suffix="%"
                  />
                </div>
              </section>
            </template>

            <!-- Expenses -->
            <section
              class="bg-gray-50 p-6 rounded-2xl border border-gray-200 shadow-sm"
            >
              <h2
                class="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2"
              >
                <i
                  class="pi pi-wallet"
                  :class="
                    editingDealType === 'BRRRR'
                      ? 'text-blue-500'
                      : 'text-orange-500'
                  "
                ></i>
                Expenses
              </h2>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <MoneyInput
                  v-if="editingDealType === 'BRRRR'"
                  :model-value="(editingDeal as any).rent ?? null"
                  @update:model-value="
                    (v: number | null) =>
                      ((editingDeal as any).rent = v ?? undefined)
                  "
                  label="Monthly Rent"
                  :required="true"
                />
                <MoneyInput
                  :model-value="
                    editingDeal.annual_property_taxes ?? null
                  "
                  @update:model-value="
                    (v: number | null) =>
                      (editingDeal!.annual_property_taxes =
                        v ?? undefined)
                  "
                  label="Annual Taxes"
                />
                <MoneyInput
                  :model-value="editingDeal.annual_insurance ?? null"
                  @update:model-value="
                    (v: number | null) =>
                      (editingDeal!.annual_insurance = v ?? undefined)
                  "
                  label="Annual Insurance"
                />
                <MoneyInput
                  :model-value="editingDeal.montly_hoa ?? null"
                  @update:model-value="
                    (v: number | null) =>
                      (editingDeal!.montly_hoa = v ?? undefined)
                  "
                  label="Monthly HOA"
                />
                <MoneyInput
                  v-if="editingDealType === 'FLIP'"
                  :model-value="
                    (editingDeal as any).monthly_utilities ?? null
                  "
                  @update:model-value="
                    (v: number | null) =>
                      ((editingDeal as any).monthly_utilities =
                        v ?? undefined)
                  "
                  label="Monthly Utilities"
                />

                <div
                  v-if="editingDealType === 'BRRRR'"
                  class="md:col-span-2 grid grid-cols-2 md:grid-cols-4 gap-3 mt-2"
                >
                  <NumberInput
                    :model-value="
                      (editingDeal as any).vacancyPercent ?? null
                    "
                    @update:model-value="
                      (v: number | null) =>
                        ((editingDeal as any).vacancyPercent =
                          v ?? undefined)
                    "
                    label="Vacancy"
                    suffix="%"
                  />
                  <NumberInput
                    :model-value="
                      (editingDeal as any).maintenancePercent ?? null
                    "
                    @update:model-value="
                      (v: number | null) =>
                        ((editingDeal as any).maintenancePercent =
                          v ?? undefined)
                    "
                    label="Maint."
                    suffix="%"
                  />
                  <NumberInput
                    :model-value="
                      (editingDeal as any).capexPercent ?? null
                    "
                    @update:model-value="
                      (v: number | null) =>
                        ((editingDeal as any).capexPercent =
                          v ?? undefined)
                    "
                    label="CapEx"
                    suffix="%"
                  />
                  <NumberInput
                    :model-value="
                      (editingDeal as any)
                        .property_managment_fee_precentages_from_rent ??
                      null
                    "
                    @update:model-value="
                      (v: number | null) =>
                        ((editingDeal as any).property_managment_fee_precentages_from_rent =
                          v ?? undefined)
                    "
                    label="Prop. Mgmt"
                    suffix="%"
                  />
                </div>
              </div>
            </section>

            <!-- Results Preview -->
            <div
              ref="analysisResultsEl"
              v-if="currentAnalysis"
              class="bg-gray-50 p-4 rounded-xl border border-gray-200 mb-6"
            >
              <h4 class="font-semibold text-gray-700 mb-3">
                Analysis Results
              </h4>
              <div
                class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm"
              >
                <template v-if="editingDealType === 'BRRRR'">
                  <div>
                    <div class="text-gray-500">Cash Flow</div>
                    <div
                      class="font-bold"
                      :class="
                        getCashFlowColor(
                          (currentAnalysis as any).cash_flow
                        )
                      "
                    >
                      {{
                        formatCurrency(
                          (currentAnalysis as any).cash_flow
                        )
                      }}
                    </div>
                  </div>
                  <div>
                    <div class="text-gray-500">Cash Out</div>
                    <div
                      class="font-bold"
                      :class="
                        getPerformanceColor(
                          (currentAnalysis as any).cash_out
                        )
                      "
                    >
                      {{
                        formatCurrency(
                          (currentAnalysis as any).cash_out
                        )
                      }}
                    </div>
                  </div>
                  <div>
                    <div class="text-gray-500">Cash Out Routi</div>
                    <div
                      class="font-bold"
                      :class="
                        getPerformanceColor(
                          (currentAnalysis as any).cash_out_routi
                        )
                      "
                    >
                      {{
                        formatCurrency(
                          (currentAnalysis as any).cash_out_routi
                        )
                      }}
                    </div>
                  </div>
                  <div>
                    <div class="text-gray-500">CoC</div>
                    <div
                      class="font-bold"
                      :class="
                        getPerformanceColor(
                          (currentAnalysis as any).cash_on_cash
                        )
                      "
                    >
                      {{
                        formatPercent(
                          (currentAnalysis as any).cash_on_cash
                        )
                      }}
                    </div>
                  </div>
                  <div>
                    <div class="text-gray-500">DSCR</div>
                    <div
                      class="font-bold"
                      :class="
                        getDSCRColor(
                          (currentAnalysis as any).dscr
                        )
                      "
                    >
                      {{
                        (currentAnalysis as any).dscr?.toFixed(2) ||
                        "-"
                      }}
                    </div>
                  </div>
                  <div>
                    <div class="text-gray-500">Equity</div>
                    <div class="font-bold text-emerald-600">
                      {{
                        formatCurrency(
                          (currentAnalysis as any).equity
                        )
                      }}
                    </div>
                  </div>
                  <div>
                    <div class="text-gray-500">ROI</div>
                    <div
                      class="font-bold"
                      :class="
                        getPerformanceColor(
                          (currentAnalysis as any).roi
                        )
                      "
                    >
                      {{
                        formatPercent(
                          (currentAnalysis as any).roi
                        )
                      }}
                    </div>
                  </div>
                  <div>
                    <div class="text-gray-500">
                      Total Cash Needed
                    </div>
                    <div class="font-bold">
                      {{
                        formatCurrency(
                          (currentAnalysis as any)
                            .total_cash_needed_for_deal
                        )
                      }}
                    </div>
                  </div>
                </template>
                <template v-else>
                  <div>
                    <div class="text-gray-500">Net Profit</div>
                    <div
                      class="font-bold"
                      :class="
                        getPerformanceColor(
                          (currentAnalysis as any).net_profit
                        )
                      "
                    >
                      {{
                        formatCurrency(
                          (currentAnalysis as any).net_profit
                        )
                      }}
                    </div>
                  </div>
                  <div>
                    <div class="text-gray-500">ROI</div>
                    <div
                      class="font-bold"
                      :class="
                        getPerformanceColor(
                          (currentAnalysis as any).roi
                        )
                      "
                    >
                      {{
                        formatPercent(
                          (currentAnalysis as any).roi
                        )
                      }}
                    </div>
                  </div>
                  <div>
                    <div class="text-gray-500">Cash Needed</div>
                    <div class="font-bold">
                      {{
                        formatCurrency(
                          (currentAnalysis as any).total_cash_needed
                        )
                      }}
                    </div>
                  </div>
                </template>
              </div>
            </div>
          </div>

          <!-- Notes -->
          <div class="mt-6">
            <label
              class="text-xs text-gray-600 font-medium uppercase mb-2 block"
              >Notes</label
            >
            <textarea
              v-model="editingDeal.notes"
              rows="4"
              class="w-full bg-gray-50 border border-gray-200 rounded-lg p-4 text-gray-900 text-sm outline-none focus:border-blue-500"
              placeholder="Additional notes..."
            ></textarea>
          </div>

          <!-- Comps Section -->
          <div class="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- Sold Comps -->
            <div class="bg-gray-50 p-4 rounded-xl border border-gray-200">
              <div class="flex justify-between items-center mb-4">
                <h4 class="font-semibold text-gray-700">Sold Comps</h4>
                <button
                  @click="editingDeal.sold_comps ? editingDeal.sold_comps.push({ url: '', arv: 0, how_long_ago: '' }) : (editingDeal.sold_comps = [{ url: '', arv: 0, how_long_ago: '' }])"
                  class="text-xs bg-blue-600 px-2 py-1 rounded text-white hover:bg-blue-500"
                >
                  <i class="pi pi-plus"></i> Add
                </button>
              </div>
              <div v-if="editingDeal.sold_comps && editingDeal.sold_comps.length > 0" class="space-y-3">
                <div v-for="(comp, index) in editingDeal.sold_comps" :key="index" class="bg-white p-2 rounded relative group border border-gray-100">
                  <button @click="editingDeal.sold_comps!.splice(index, 1)" class="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity z-10">x</button>
                  <div class="flex items-center gap-2 mb-1">
                    <input v-model="comp.url" placeholder="URL" class="flex-1 bg-transparent border-b border-gray-100 text-xs focus:border-blue-500 outline-none text-gray-700" />
                    <a v-if="comp.url" :href="comp.url" target="_blank" class="text-xs text-blue-500 hover:text-blue-700 flex-none"><i class="pi pi-external-link"></i></a>
                  </div>
                  <div class="flex gap-2">
                    <input v-model="comp.arv" type="number" placeholder="ARV" class="w-1/2 bg-transparent border-b border-gray-100 text-xs focus:border-blue-500 outline-none text-gray-700" />
                    <input v-model="comp.how_long_ago" placeholder="When?" class="w-1/2 bg-transparent border-b border-gray-100 text-xs focus:border-blue-500 outline-none text-gray-700" />
                  </div>
                </div>
              </div>
              <div v-else class="text-xs text-gray-400 italic text-center py-4">No sold comps added</div>
            </div>

            <!-- Rent Comps / Sale Comps -->
            <div class="bg-gray-50 p-4 rounded-xl border border-gray-200">
              <div class="flex justify-between items-center mb-4">
                <h4 class="font-semibold text-gray-700">
                  {{ editingDealType === 'FLIP' ? 'For Sale Comps' : 'Rent Comps' }}
                </h4>
                <button
                  @click="editingDealType === 'FLIP' ? ((editingDeal as any).sale_comps ? (editingDeal as any).sale_comps.push({ url: '', arv: 0, how_long_ago: '' }) : ((editingDeal as any).sale_comps = [{ url: '', arv: 0, how_long_ago: '' }])) : (editingDeal.rent_comps ? editingDeal.rent_comps.push({ url: '', rent: 0, time_on_market: '' }) : (editingDeal.rent_comps = [{ url: '', rent: 0, time_on_market: '' }]))"
                  class="text-xs bg-blue-600 px-2 py-1 rounded text-white hover:bg-blue-500"
                >
                  <i class="pi pi-plus"></i> Add
                </button>
              </div>

              <!-- Flip Sale Comps -->
              <div v-if="editingDealType === 'FLIP'">
                <div v-if="(editingDeal as any).sale_comps && (editingDeal as any).sale_comps.length > 0" class="space-y-3">
                  <div v-for="(comp, index) in (editingDeal as any).sale_comps" :key="index" class="bg-white p-2 rounded relative group border border-gray-100">
                    <button @click="(editingDeal as any).sale_comps!.splice(index, 1)" class="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity z-10">x</button>
                    <div class="flex items-center gap-2 mb-1">
                      <input v-model="comp.url" placeholder="URL" class="flex-1 bg-transparent border-b border-gray-100 text-xs focus:border-blue-500 outline-none text-gray-700" />
                      <a v-if="comp.url" :href="comp.url" target="_blank" class="text-xs text-blue-500 hover:text-blue-700 flex-none"><i class="pi pi-external-link"></i></a>
                    </div>
                    <div class="flex gap-2">
                      <input v-model="comp.arv" type="number" placeholder="List Price" class="w-1/2 bg-transparent border-b border-gray-100 text-xs focus:border-blue-500 outline-none text-gray-700" />
                      <input v-model="comp.how_long_ago" placeholder="Days on Mkt" class="w-1/2 bg-transparent border-b border-gray-100 text-xs focus:border-blue-500 outline-none text-gray-700" />
                    </div>
                  </div>
                </div>
                <div v-else class="text-xs text-gray-400 italic text-center py-4">No active comps added</div>
              </div>

              <!-- BRRRR Rent Comps -->
              <div v-else>
                <div v-if="editingDeal.rent_comps && editingDeal.rent_comps.length > 0" class="space-y-3">
                  <div v-for="(comp, index) in editingDeal.rent_comps" :key="index" class="bg-white p-2 rounded relative group border border-gray-100">
                    <button @click="editingDeal.rent_comps!.splice(index, 1)" class="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity z-10">x</button>
                    <div class="flex items-center gap-2 mb-1">
                      <input v-model="comp.url" placeholder="URL" class="flex-1 bg-transparent border-b border-gray-100 text-xs focus:border-blue-500 outline-none text-gray-700" />
                      <a v-if="comp.url" :href="comp.url" target="_blank" class="text-xs text-blue-500 hover:text-blue-700 flex-none"><i class="pi pi-external-link"></i></a>
                    </div>
                    <div class="flex gap-2">
                      <input v-model="comp.rent" type="number" placeholder="Rent" class="w-1/2 bg-transparent border-b border-gray-100 text-xs focus:border-blue-500 outline-none text-gray-700" />
                      <input v-model="comp.time_on_market" placeholder="Time on Market" class="w-1/2 bg-transparent border-b border-gray-100 text-xs focus:border-blue-500 outline-none text-gray-700" />
                    </div>
                  </div>
                </div>
                <div v-else class="text-xs text-gray-400 italic text-center py-4">No rent comps added</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div
          class="p-6 border-t border-gray-200 flex justify-between items-center bg-gray-50 rounded-b-2xl"
        >
          <div class="text-xs text-gray-500">
            Created:
            {{
              new Date(editingDeal.created_at).toLocaleDateString()
            }}
          </div>
          <div class="flex items-center gap-4">
            <div
              class="flex items-center gap-1.5 text-xs transition-opacity duration-300"
            >
              <template v-if="saveStatus === 'saving'">
                <i class="pi pi-spin pi-spinner text-blue-500"></i>
                <span class="text-blue-500">Saving...</span>
              </template>
              <template v-else-if="saveStatus === 'saved'">
                <i class="pi pi-check-circle text-emerald-500"></i>
                <span class="text-emerald-500">Saved</span>
              </template>
              <template v-else-if="saveStatus === 'error'">
                <i
                  class="pi pi-exclamation-circle text-red-500"
                ></i>
                <span class="text-red-500">Save failed</span>
              </template>
            </div>
            <button
              @click="deleteEditingDeal"
              class="text-red-600 hover:text-red-800 px-4 py-2 flex items-center gap-2"
            >
              <i class="pi pi-trash"></i> Delete
            </button>
            <button
              @click="closeModal"
              class="text-gray-500 hover:text-gray-700 px-4 py-2 flex items-center gap-2"
            >
              <i class="pi pi-times"></i> Close
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
