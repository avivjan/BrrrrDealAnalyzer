<script setup lang="ts">
/** Saving / Saved / Offline (n queued) / error, for the sticky header. */
import { computed } from "vue";

import type { InspectionSaveState } from "../../stores/inspectionStore";

const props = defineProps<{ saveState: InspectionSaveState; pendingChangeCount: number; errorMessage: string | null }>();

const uiSaveStatus = computed(() => (props.saveState === "offline" ? "error" : props.saveState));
</script>

<template>
  <span v-if="saveState === 'offline'" role="status" aria-live="polite" data-testid="inspection.save-status" class="inline-flex items-center gap-1.5 text-xs font-medium text-warning">
    <i class="pi pi-wifi" aria-hidden="true"></i>Offline · {{ pendingChangeCount }} {{ pendingChangeCount === 1 ? "change" : "changes" }} queued
  </span>
  <UiSaveStatus v-else :status="uiSaveStatus" data-testid="inspection.save-status">
    <template v-if="saveState === 'saving'">Saving…</template>
    <template v-else-if="saveState === 'saved'">Saved</template>
    <template v-else-if="saveState === 'error'">{{ errorMessage || "Not saved" }}</template>
  </UiSaveStatus>
</template>
