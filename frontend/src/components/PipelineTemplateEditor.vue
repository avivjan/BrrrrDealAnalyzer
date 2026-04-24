<script setup lang="ts">
/**
 * Pipeline template editor modal.
 *
 * Opens from the Bought Deals header, shows BRRRR vs FLIP as two tabs, and
 * lets the user add / rename / delete / reorder stages and substages.
 *
 * Stable IDs live inside each stage/substage; renames change only `name` /
 * `label`. Reorder swaps array order but never rewrites IDs. Deletion warns
 * when existing deals reference the affected ids, but never blocks.
 */

import { computed, ref, watch } from "vue";
import { VueDraggable } from "vue-draggable-plus";
import { usePipelineTemplateStore } from "../stores/pipelineTemplateStore";
import type { PipelineStageDto, PipelineTemplateStats } from "../types";
import {
  newStageId,
  newSubStageId,
} from "../config/boughtDealStages";

const props = defineProps<{
  open: boolean;
  initialTab?: "BRRRR" | "FLIP";
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "saved"): void;
}>();

const pipelineStore = usePipelineTemplateStore();

type DealType = "BRRRR" | "FLIP";
const activeTab = ref<DealType>(props.initialTab ?? "BRRRR");

/** Working draft – never mutate the store directly; commit via saveTemplate. */
const draftByType = ref<Record<DealType, PipelineStageDto[]>>({
  BRRRR: clone(pipelineStore.brrrStages),
  FLIP: clone(pipelineStore.flipStages),
});

const statsByType = ref<Record<DealType, PipelineTemplateStats | null>>({
  BRRRR: null,
  FLIP: null,
});

const saveError = ref<string | null>(null);

function clone<T>(val: T): T {
  return JSON.parse(JSON.stringify(val));
}

// --- Open / tab lifecycle ------------------------------------------------

watch(
  () => props.open,
  async (isOpen) => {
    if (!isOpen) return;
    activeTab.value = props.initialTab ?? "BRRRR";
    await pipelineStore.fetchTemplates();
    draftByType.value = {
      BRRRR: clone(pipelineStore.brrrStages),
      FLIP: clone(pipelineStore.flipStages),
    };
    saveError.value = null;
    await Promise.all([loadStats("BRRRR"), loadStats("FLIP")]);
  },
);

async function loadStats(type: DealType) {
  statsByType.value[type] = await pipelineStore.fetchStats(type);
}

// --- Helpers over the current tab's draft --------------------------------

const currentStages = computed({
  get: () => draftByType.value[activeTab.value],
  set: (val) => {
    draftByType.value[activeTab.value] = val;
  },
});

const currentStats = computed(() => statsByType.value[activeTab.value]);

function stageDealCount(stageId: string): number {
  const stat = currentStats.value?.stages.find((s) => s.stageId === stageId);
  return stat?.dealCount ?? 0;
}

function substageCompletions(stageId: string, substageId: string): number {
  const stage = currentStats.value?.stages.find((s) => s.stageId === stageId);
  const sub = stage?.substages.find((s) => s.substageId === substageId);
  return sub?.dealsWithCompletion ?? 0;
}

// --- Stage mutations -----------------------------------------------------

function addStage() {
  currentStages.value = [
    ...currentStages.value,
    { id: newStageId(), name: "New Stage", subStages: [] },
  ];
}

function removeStage(index: number) {
  const stage = currentStages.value[index];
  if (!stage) return;
  const count = stageDealCount(stage.id);
  const msg =
    count > 0
      ? `Delete stage "${stage.name}"? ${count} deal(s) are currently on this stage and will be clamped to the nearest remaining stage.`
      : `Delete stage "${stage.name}"?`;
  if (!confirm(msg)) return;
  currentStages.value = currentStages.value.filter((_, i) => i !== index);
}

function moveStage(index: number, delta: -1 | 1) {
  const next = [...currentStages.value];
  const target = index + delta;
  if (target < 0 || target >= next.length) return;
  const tmp = next[index]!;
  next[index] = next[target]!;
  next[target] = tmp;
  currentStages.value = next;
}

// --- Substage mutations ---------------------------------------------------

function addSubstage(stageIndex: number) {
  const next = [...currentStages.value];
  const stage = next[stageIndex];
  if (!stage) return;
  stage.subStages = [
    ...stage.subStages,
    { id: newSubStageId(), label: "New Sub-stage" },
  ];
  currentStages.value = next;
}

function removeSubstage(stageIndex: number, subIndex: number) {
  const stage = currentStages.value[stageIndex];
  if (!stage) return;
  const sub = stage.subStages[subIndex];
  if (!sub) return;
  const completions = substageCompletions(stage.id, sub.id);
  const msg =
    completions > 0
      ? `Delete substage "${sub.label}"? ${completions} deal(s) have completions for this substage. The legacy data will be ignored (not blocking advance) but kept on the deal.`
      : `Delete substage "${sub.label}"?`;
  if (!confirm(msg)) return;
  const next = [...currentStages.value];
  next[stageIndex] = {
    ...stage,
    subStages: stage.subStages.filter((_, i) => i !== subIndex),
  };
  currentStages.value = next;
}

function moveSubstage(stageIndex: number, subIndex: number, delta: -1 | 1) {
  const stage = currentStages.value[stageIndex];
  if (!stage) return;
  const target = subIndex + delta;
  if (target < 0 || target >= stage.subStages.length) return;
  const nextSubs = [...stage.subStages];
  const tmp = nextSubs[subIndex]!;
  nextSubs[subIndex] = nextSubs[target]!;
  nextSubs[target] = tmp;
  const next = [...currentStages.value];
  next[stageIndex] = { ...stage, subStages: nextSubs };
  currentStages.value = next;
}

// --- Validation ----------------------------------------------------------

const validationIssues = computed<string[]>(() => {
  const issues: string[] = [];
  const stages = currentStages.value;
  if (!stages.length) {
    issues.push("Pipeline must have at least one stage.");
    return issues;
  }
  const stageIds = new Set<string>();
  for (const s of stages) {
    if (!s.name?.trim()) issues.push(`Stage "${s.id}" has no name.`);
    if (stageIds.has(s.id)) issues.push(`Duplicate stage id: "${s.id}".`);
    stageIds.add(s.id);
    const subIds = new Set<string>();
    for (const sub of s.subStages) {
      if (!sub.label?.trim())
        issues.push(`Substage "${sub.id}" (in ${s.name}) has no label.`);
      if (subIds.has(sub.id))
        issues.push(`Duplicate substage id "${sub.id}" in "${s.name}".`);
      subIds.add(sub.id);
    }
  }
  return issues;
});

const canSave = computed(
  () => validationIssues.value.length === 0 && !pipelineStore.isSaving,
);

// --- Save / close --------------------------------------------------------

async function save() {
  saveError.value = null;
  try {
    await pipelineStore.saveTemplate(activeTab.value, currentStages.value);
    emit("saved");
  } catch (err: any) {
    saveError.value =
      err?.response?.data?.detail?.toString?.() ?? "Failed to save pipeline";
  }
}

async function saveAndClose() {
  await save();
  if (!saveError.value) emit("close");
}

function close() {
  emit("close");
}
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
    @click.self="close"
  >
    <div
      class="bg-white w-full max-w-4xl max-h-[95vh] rounded-2xl border border-gray-200 shadow-2xl flex flex-col"
    >
      <!-- Header -->
      <div
        class="flex justify-between items-center p-5 border-b border-gray-100 shrink-0"
      >
        <div>
          <h2 class="text-xl font-bold text-gray-900 flex items-center gap-2">
            <i class="pi pi-sliders-v text-blue-500"></i>
            Edit Pipeline Template
          </h2>
          <p class="text-xs text-gray-500 mt-0.5">
            Stages and substages for the Bought Deals board. IDs are stable —
            renames and reorders don't affect existing deals.
          </p>
        </div>
        <button
          @click="close"
          class="text-gray-400 hover:text-gray-600"
          title="Close"
        >
          <i class="pi pi-times text-xl"></i>
        </button>
      </div>

      <!-- Tabs -->
      <div class="flex items-center justify-between px-5 pt-4">
        <div class="flex bg-gray-100 rounded-lg p-1 border border-gray-200">
          <button
            v-for="tab in (['BRRRR', 'FLIP'] as const)"
            :key="tab"
            @click="activeTab = tab"
            class="px-3 py-1.5 text-sm font-medium rounded-md transition-all"
            :class="
              activeTab === tab
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            "
          >
            {{ tab === "BRRRR" ? "BRRRR" : "Flip" }}
          </button>
        </div>
        <div class="text-xs text-gray-500">
          Editing
          <span
            class="px-2 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wide border ml-1"
            :class="
              activeTab === 'BRRRR'
                ? 'bg-blue-100 text-blue-700 border-blue-200'
                : 'bg-orange-100 text-orange-700 border-orange-200'
            "
          >
            {{ activeTab }}
          </span>
          pipeline
        </div>
      </div>

      <!-- Validation banner -->
      <div
        v-if="validationIssues.length"
        class="mx-5 mt-3 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm"
      >
        <div class="font-semibold mb-1">Please fix before saving:</div>
        <ul class="list-disc pl-5 space-y-0.5">
          <li v-for="issue in validationIssues" :key="issue">{{ issue }}</li>
        </ul>
      </div>

      <div
        v-if="saveError"
        class="mx-5 mt-3 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm"
      >
        {{ saveError }}
      </div>

      <!-- Stage list -->
      <div class="flex-1 overflow-y-auto custom-scrollbar p-5 space-y-3">
        <VueDraggable
          v-model="currentStages"
          handle=".stage-drag-handle"
          :animation="150"
          class="space-y-3"
          ghost-class="opacity-50"
        >
          <div
            v-for="(stage, stageIdx) in currentStages"
            :key="stage.id"
            class="rounded-xl border border-gray-200 bg-white shadow-sm"
          >
            <!-- Stage header row -->
            <div
              class="flex items-center gap-3 p-3 border-b border-gray-100 bg-gray-50/60 rounded-t-xl"
            >
              <button
                class="stage-drag-handle text-gray-400 hover:text-gray-600 cursor-grab active:cursor-grabbing"
                title="Drag to reorder"
              >
                <i class="pi pi-bars"></i>
              </button>
              <input
                v-model="stage.name"
                class="flex-1 bg-transparent text-base font-semibold text-gray-900 border-b border-transparent hover:border-gray-200 focus:border-blue-500 outline-none transition-colors"
                placeholder="Stage name"
              />
              <span
                class="text-[10px] font-mono text-gray-400 truncate max-w-[140px]"
                :title="stage.id"
              >
                {{ stage.id }}
              </span>
              <span
                v-if="stageDealCount(stage.id) > 0"
                class="text-[11px] font-medium bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full border border-amber-200"
                :title="`${stageDealCount(stage.id)} deal(s) on this stage`"
              >
                {{ stageDealCount(stage.id) }} deal{{
                  stageDealCount(stage.id) === 1 ? "" : "s"
                }}
              </span>
              <div class="flex items-center gap-1">
                <button
                  @click="moveStage(stageIdx, -1)"
                  :disabled="stageIdx === 0"
                  class="text-gray-400 hover:text-gray-700 disabled:opacity-30 disabled:cursor-not-allowed px-1"
                  title="Move up"
                >
                  <i class="pi pi-arrow-up text-xs"></i>
                </button>
                <button
                  @click="moveStage(stageIdx, 1)"
                  :disabled="stageIdx === currentStages.length - 1"
                  class="text-gray-400 hover:text-gray-700 disabled:opacity-30 disabled:cursor-not-allowed px-1"
                  title="Move down"
                >
                  <i class="pi pi-arrow-down text-xs"></i>
                </button>
                <button
                  @click="removeStage(stageIdx)"
                  class="text-red-500 hover:text-red-700 px-1"
                  title="Delete stage"
                >
                  <i class="pi pi-trash text-xs"></i>
                </button>
              </div>
            </div>

            <!-- Substages -->
            <div class="p-3 space-y-2">
              <div
                v-if="stage.subStages.length === 0"
                class="text-xs italic text-gray-400 px-2 py-1"
              >
                No substages.
              </div>
              <div
                v-for="(sub, subIdx) in stage.subStages"
                :key="sub.id"
                class="flex items-center gap-2 bg-gray-50 border border-gray-100 rounded-lg px-2.5 py-1.5"
              >
                <i class="pi pi-check-square text-xs text-gray-400"></i>
                <input
                  v-model="sub.label"
                  class="flex-1 bg-transparent text-sm text-gray-800 border-b border-transparent hover:border-gray-200 focus:border-blue-500 outline-none"
                  placeholder="Substage label"
                />
                <span
                  class="text-[10px] font-mono text-gray-400 truncate max-w-[120px]"
                  :title="sub.id"
                >
                  {{ sub.id }}
                </span>
                <span
                  v-if="substageCompletions(stage.id, sub.id) > 0"
                  class="text-[10px] bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded-full border border-blue-200"
                  :title="`${substageCompletions(stage.id, sub.id)} deal(s) have completions`"
                >
                  {{ substageCompletions(stage.id, sub.id) }}
                </span>
                <button
                  @click="moveSubstage(stageIdx, subIdx, -1)"
                  :disabled="subIdx === 0"
                  class="text-gray-400 hover:text-gray-700 disabled:opacity-30"
                  title="Move up"
                >
                  <i class="pi pi-arrow-up text-[10px]"></i>
                </button>
                <button
                  @click="moveSubstage(stageIdx, subIdx, 1)"
                  :disabled="subIdx === stage.subStages.length - 1"
                  class="text-gray-400 hover:text-gray-700 disabled:opacity-30"
                  title="Move down"
                >
                  <i class="pi pi-arrow-down text-[10px]"></i>
                </button>
                <button
                  @click="removeSubstage(stageIdx, subIdx)"
                  class="text-red-400 hover:text-red-600"
                  title="Delete substage"
                >
                  <i class="pi pi-times text-[10px]"></i>
                </button>
              </div>
              <button
                @click="addSubstage(stageIdx)"
                class="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1 mt-1"
              >
                <i class="pi pi-plus text-[10px]"></i> Add substage
              </button>
            </div>
          </div>
        </VueDraggable>

        <button
          @click="addStage"
          class="w-full mt-2 py-2 rounded-lg border-2 border-dashed border-gray-300 text-gray-500 hover:text-blue-600 hover:border-blue-400 text-sm font-medium transition-colors flex items-center justify-center gap-2"
        >
          <i class="pi pi-plus"></i> Add stage
        </button>

        <p
          v-if="currentStats && currentStats.orphanStageDealCount > 0"
          class="text-xs text-amber-700 bg-amber-50 border border-amber-200 px-3 py-2 rounded-lg mt-2"
        >
          <i class="pi pi-exclamation-triangle"></i>
          {{ currentStats.orphanStageDealCount }} deal(s) currently reference a
          stage that doesn't exist in this template. They will be clamped to
          the first stage until moved.
        </p>
      </div>

      <!-- Footer -->
      <div
        class="p-4 border-t border-gray-200 flex items-center justify-between bg-gray-50 rounded-b-2xl"
      >
        <div class="text-xs text-gray-500">
          Changes affect the
          <strong>{{ activeTab }}</strong>
          pipeline. Existing deals keep their stage references via stable IDs.
        </div>
        <div class="flex items-center gap-2">
          <button
            @click="close"
            class="px-4 py-2 rounded-lg text-sm text-gray-600 hover:text-gray-900"
          >
            Cancel
          </button>
          <button
            @click="saveAndClose"
            :disabled="!canSave"
            class="px-4 py-2 rounded-lg text-sm font-semibold text-white bg-blue-600 hover:bg-blue-500 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <i v-if="pipelineStore.isSaving" class="pi pi-spin pi-spinner"></i>
            <i v-else class="pi pi-save"></i>
            Save
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
