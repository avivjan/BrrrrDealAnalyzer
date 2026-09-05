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
    data-testid="pipeline.root"
    class="fixed inset-0 z-[60] flex items-center justify-center bg-fg/40 p-4 md:backdrop-blur-sm"
    @click.self="close"
  >
    <UiModalPanel size="lg" labelled-by="pipeline-editor-title">
      <!-- Header -->
      <template #header>
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <h2
              id="pipeline-editor-title"
              class="flex items-center gap-2 text-base font-semibold text-fg md:text-lg"
            >
              <i class="pi pi-sliders-v text-primary" aria-hidden="true"></i>
              Edit Pipeline Template
            </h2>
            <p class="mt-1 text-xs text-fg-muted">
              Stages and substages for the Bought Deals board. IDs are stable —
              renames and reorders don't affect existing deals.
            </p>
          </div>
          <UiIconButton
            data-testid="pipeline.close"
            @click="close"
            title="Close"
            label="Close"
            size="md"
          >
            <i class="pi pi-times text-xl" aria-hidden="true"></i>
          </UiIconButton>
        </div>
      </template>

      <!-- Tabs -->
      <div class="flex flex-wrap items-center justify-between gap-3">
        <UiTabs aria-label="Pipeline deal type">
          <UiButton
            v-for="tab in (['BRRRR', 'FLIP'] as const)"
            :key="tab"
            :data-testid="`pipeline.tab.${tab}`"
            @click="activeTab = tab"
            variant="tab"
            size="sm"
            :active="activeTab === tab"
            class="min-h-9 touch:min-h-11 px-3"
          >
            {{ tab === "BRRRR" ? "BRRRR" : "Flip" }}
          </UiButton>
        </UiTabs>
        <div class="flex items-center gap-1.5 text-xs text-fg-muted">
          Editing
          <UiBadge
            :deal-type="activeTab"
            class="font-bold uppercase tracking-wide"
          >
            {{ activeTab }}
          </UiBadge>
          pipeline
        </div>
      </div>

      <!-- Validation banner -->
      <UiCard
        v-if="validationIssues.length"
        data-testid="pipeline.validation-banner"
        tone="muted"
        padding="sm"
        class="mt-4 border-negative/30 bg-negative/10 text-sm text-negative"
      >
        <div class="mb-1 flex items-center gap-2 font-semibold">
          <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
          Please fix before saving:
        </div>
        <ul class="list-disc space-y-0.5 pl-5">
          <li
            v-for="issue in validationIssues"
            :key="issue"
            :data-testid="`pipeline.issue.${issue}`"
          >
            {{ issue }}
          </li>
        </ul>
      </UiCard>

      <UiCard
        v-if="saveError"
        data-testid="pipeline.save-error"
        tone="muted"
        padding="sm"
        class="mt-4 flex items-center gap-2 border-negative/30 bg-negative/10 text-sm text-negative"
      >
        <i class="pi pi-exclamation-circle" aria-hidden="true"></i>
        {{ saveError }}
      </UiCard>

      <!-- Stage list -->
      <div class="mt-4 space-y-3">
        <VueDraggable
          data-testid="pipeline.stages-draggable"
          v-model="currentStages"
          handle=".stage-drag-handle"
          :animation="150"
          class="space-y-3"
          ghost-class="opacity-50"
        >
          <UiCard
            v-for="(stage, stageIdx) in currentStages"
            :key="stage.id"
            :data-testid="`pipeline.stage.${stageIdx}`"
            padding="sm"
          >
            <!-- Stage header row -->
            <template #header>
              <div class="flex flex-wrap items-center gap-2">
                <UiIconButton
                  :data-testid="`pipeline.stage.${stageIdx}.drag`"
                  class="stage-drag-handle cursor-grab active:cursor-grabbing"
                  title="Drag to reorder"
                  label="Drag to reorder"
                >
                  <i class="pi pi-bars" aria-hidden="true"></i>
                </UiIconButton>
                <input
                  :data-testid="`pipeline.stage.${stageIdx}.name`"
                  v-model="stage.name"
                  class="ui-input min-w-0 flex-1 basis-40 font-semibold"
                  placeholder="Stage name"
                />
                <span
                  class="max-w-[140px] truncate font-mono text-[10px] text-fg-muted"
                  :title="stage.id"
                >
                  {{ stage.id }}
                </span>
                <UiBadge
                  v-if="stageDealCount(stage.id) > 0"
                  tone="warning"
                  :title="`${stageDealCount(stage.id)} deal(s) on this stage`"
                >
                  {{ stageDealCount(stage.id) }} deal{{
                    stageDealCount(stage.id) === 1 ? "" : "s"
                  }}
                </UiBadge>
                <div class="ml-auto flex items-center gap-2">
                  <UiIconButton
                    :data-testid="`pipeline.stage.${stageIdx}.move-up`"
                    @click="moveStage(stageIdx, -1)"
                    :disabled="stageIdx === 0"
                    title="Move up"
                    label="Move stage up"
                  >
                    <i class="pi pi-arrow-up text-xs" aria-hidden="true"></i>
                  </UiIconButton>
                  <UiIconButton
                    :data-testid="`pipeline.stage.${stageIdx}.move-down`"
                    @click="moveStage(stageIdx, 1)"
                    :disabled="stageIdx === currentStages.length - 1"
                    title="Move down"
                    label="Move stage down"
                  >
                    <i class="pi pi-arrow-down text-xs" aria-hidden="true"></i>
                  </UiIconButton>
                  <UiIconButton
                    :data-testid="`pipeline.stage.${stageIdx}.delete`"
                    @click="removeStage(stageIdx)"
                    title="Delete stage"
                    label="Delete stage"
                    variant="danger"
                  >
                    <i class="pi pi-trash text-xs" aria-hidden="true"></i>
                  </UiIconButton>
                </div>
              </div>
            </template>

            <!-- Substages -->
            <div class="space-y-2">
              <UiEmptyState
                v-if="stage.subStages.length === 0"
                :data-testid="`pipeline.stage.${stageIdx}.substages-empty`"
                class="items-start px-3 py-2 text-left"
              >
                No substages.
              </UiEmptyState>
              <div
                v-for="(sub, subIdx) in stage.subStages"
                :key="sub.id"
                :data-testid="`pipeline.substage.${sub.id}`"
                class="flex flex-wrap items-center gap-2 rounded-ctl border border-line bg-surface-muted px-2.5 py-1.5"
              >
                <i
                  class="pi pi-check-square text-xs text-fg-muted"
                  aria-hidden="true"
                ></i>
                <input
                  :data-testid="`pipeline.substage.${sub.id}.name`"
                  v-model="sub.label"
                  class="ui-input min-w-0 flex-1 basis-32 text-sm"
                  placeholder="Substage label"
                />
                <span
                  class="max-w-[120px] truncate font-mono text-[10px] text-fg-muted"
                  :title="sub.id"
                >
                  {{ sub.id }}
                </span>
                <UiBadge
                  v-if="substageCompletions(stage.id, sub.id) > 0"
                  tone="info"
                  :title="`${substageCompletions(stage.id, sub.id)} deal(s) have completions`"
                >
                  {{ substageCompletions(stage.id, sub.id) }}
                </UiBadge>
                <div class="ml-auto flex items-center gap-2">
                  <UiIconButton
                    :data-testid="`pipeline.substage.${sub.id}.move-up`"
                    @click="moveSubstage(stageIdx, subIdx, -1)"
                    :disabled="subIdx === 0"
                    title="Move up"
                    label="Move sub-stage up"
                  >
                    <i class="pi pi-arrow-up text-[10px]" aria-hidden="true"></i>
                  </UiIconButton>
                  <UiIconButton
                    :data-testid="`pipeline.substage.${sub.id}.move-down`"
                    @click="moveSubstage(stageIdx, subIdx, 1)"
                    :disabled="subIdx === stage.subStages.length - 1"
                    title="Move down"
                    label="Move sub-stage down"
                  >
                    <i
                      class="pi pi-arrow-down text-[10px]"
                      aria-hidden="true"
                    ></i>
                  </UiIconButton>
                  <UiIconButton
                    :data-testid="`pipeline.substage.${sub.id}.delete`"
                    @click="removeSubstage(stageIdx, subIdx)"
                    title="Delete substage"
                    label="Delete sub-stage"
                    variant="danger"
                  >
                    <i class="pi pi-times text-[10px]" aria-hidden="true"></i>
                  </UiIconButton>
                </div>
              </div>
              <UiButton
                :data-testid="`pipeline.stage.${stageIdx}.add-substage`"
                @click="addSubstage(stageIdx)"
                variant="ghost"
                size="sm"
                class="mt-1 min-h-9 touch:min-h-11 text-primary hover:text-primary-hover"
              >
                <i class="pi pi-plus text-[10px]" aria-hidden="true"></i> Add
                substage
              </UiButton>
            </div>
          </UiCard>
        </VueDraggable>

        <UiButton
          data-testid="pipeline.add-stage"
          @click="addStage"
          variant="ghost"
          block
          class="mt-2 border-2 border-dashed border-line text-fg-muted hover:border-primary hover:bg-transparent hover:text-primary"
        >
          <i class="pi pi-plus" aria-hidden="true"></i> Add stage
        </UiButton>

        <p
          v-if="currentStats && currentStats.orphanStageDealCount > 0"
          data-testid="pipeline.orphan-banner"
          class="mt-2 rounded-ctl border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning"
        >
          <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
          {{ currentStats.orphanStageDealCount }} deal(s) currently reference a
          stage that doesn't exist in this template. They will be clamped to
          the first stage until moved.
        </p>
      </div>

      <!-- Footer -->
      <template #footer>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="text-xs text-fg-muted">
            Changes affect the
            <strong>{{ activeTab }}</strong>
            pipeline. Existing deals keep their stage references via stable IDs.
          </div>
          <div class="ml-auto flex items-center gap-2">
            <UiButton
              data-testid="pipeline.cancel"
              @click="close"
              variant="ghost"
              size="sm"
              class="min-h-11"
            >
              Cancel
            </UiButton>
            <UiButton
              data-testid="pipeline.save"
              @click="saveAndClose"
              :disabled="!canSave"
              size="sm"
              class="min-h-11 font-semibold"
            >
              <i
                v-if="pipelineStore.isSaving"
                class="pi pi-spin pi-spinner"
                aria-hidden="true"
              ></i>
              <i v-else class="pi pi-save" aria-hidden="true"></i>
              Save
            </UiButton>
          </div>
        </div>
      </template>
    </UiModalPanel>
  </div>
</template>
