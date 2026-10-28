<script setup lang="ts">
/**
 * "Finish anyway": shown only while CRITICAL items are still not checked.
 * The inspection can be finished early, but only with a typed reason of at
 * least 10 characters, which is stored with the inspection.
 */
import { computed, ref } from "vue";

import { MINIMUM_COMPLETION_OVERRIDE_REASON_LENGTH, isCompletionOverrideReasonAcceptable } from "../../inspection/inspectionChecklistLogic";

defineProps<{ remainingCriticalItemLabels: string[]; isSubmitting: boolean; errorMessage: string | null }>();
const emit = defineEmits<{ cancel: []; confirm: [reason: string] }>();

const overrideReason = ref("");
const canConfirm = computed(() => isCompletionOverrideReasonAcceptable(overrideReason.value));
</script>

<template>
  <Teleport to="body">
  <div class="inspection-fade-in fixed inset-0 z-[800] flex items-center justify-center bg-fg/40 p-4 md:backdrop-blur-sm" @click.self="emit('cancel')" @keydown.esc="emit('cancel')">
  <UiModalPanel size="sm" labelled-by="inspection-finish-anyway-title" data-testid="inspection.finish-dialog">
    <template #header>
      <h2 id="inspection-finish-anyway-title" class="font-display text-2xl text-fg">Finish without every mission?</h2>
    </template>
    <p class="text-base text-fg-muted">These expensive systems are still not checked:</p>
    <ul role="list" class="mt-3 flex flex-wrap gap-2">
      <li v-for="label in remainingCriticalItemLabels" :key="label" class="inline-flex min-h-9 items-center gap-1.5 rounded-full border border-accent/50 bg-accent/10 px-3 text-sm font-medium text-fg">
        <i class="pi pi-bolt text-xs text-accent" aria-hidden="true"></i>{{ label }}
      </li>
    </ul>
    <label class="mt-5 block">
      <span class="mb-2 block text-base font-semibold text-fg">Why finish now?</span>
      <textarea
        v-model="overrideReason"
        data-testid="inspection.finish-dialog.reason"
        rows="3"
        maxlength="500"
        placeholder="e.g. No access to the attic; the roofer inspects it Monday"
        class="ui-textarea w-full text-base"
      ></textarea>
      <span class="mt-1 block text-xs text-fg-muted">At least {{ MINIMUM_COMPLETION_OVERRIDE_REASON_LENGTH }} characters. Saved with the inspection.</span>
    </label>
    <p v-if="errorMessage" role="alert" class="mt-3 text-sm text-negative">{{ errorMessage }}</p>
    <template #footer>
      <div class="flex flex-wrap justify-end gap-2">
        <UiButton variant="secondary" size="lg" data-testid="inspection.finish-dialog.cancel" @click="emit('cancel')">Keep inspecting</UiButton>
        <UiButton variant="danger" size="lg" data-testid="inspection.finish-dialog.confirm" :disabled="!canConfirm || isSubmitting" :loading="isSubmitting" @click="emit('confirm', overrideReason.trim())">
          Finish anyway
        </UiButton>
      </div>
    </template>
  </UiModalPanel>
  </div>
  </Teleport>
</template>
