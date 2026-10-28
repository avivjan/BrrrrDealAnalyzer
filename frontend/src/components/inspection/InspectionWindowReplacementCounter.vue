<script setup lang="ts">
/**
 * "How many windows need replacement": a single number set with huge −/+
 * steppers, never typed. Stays within the field's configured bounds.
 */
import { computed } from "vue";

import { clampCounterValue, type InspectionFieldConfig } from "../../inspection/inspectionChecklistLogic";

const props = defineProps<{ field: InspectionFieldConfig; modelValue: number | undefined }>();
const emit = defineEmits<{ "update:modelValue": [count: number] }>();

const currentCount = computed(() => (typeof props.modelValue === "number" ? props.modelValue : 0));
const minimumCount = computed(() => props.field.minimum_count ?? 0);
const maximumCount = computed(() => props.field.maximum_count ?? 99);

function step(by: number) {
  emit("update:modelValue", clampCounterValue(props.field, currentCount.value + by));
}
</script>

<template>
  <div class="flex items-center justify-between gap-4 rounded-card border border-line bg-surface-2/60 p-3">
    <button
      type="button"
      data-testid="inspection.counter.decrease"
      :aria-label="`One fewer: ${field.label}`"
      :disabled="currentCount <= minimumCount"
      class="inspection-press grid size-[72px] shrink-0 place-items-center rounded-full border-2 border-line bg-surface text-3xl text-fg disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      @click="step(-1)"
    >
      <i class="pi pi-minus" aria-hidden="true"></i>
    </button>
    <div class="text-center" aria-live="polite">
      <span data-testid="inspection.counter.value" class="numeric block font-display text-6xl leading-none text-fg">{{ currentCount }}</span>
      <span class="mt-1 block text-sm text-fg-muted">{{ currentCount === 1 ? "window" : "windows" }}</span>
    </div>
    <button
      type="button"
      data-testid="inspection.counter.increase"
      :aria-label="`One more: ${field.label}`"
      :disabled="currentCount >= maximumCount"
      class="inspection-press grid size-[72px] shrink-0 place-items-center rounded-full bg-primary text-3xl text-primary-fg shadow-2 disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      @click="step(1)"
    >
      <i class="pi pi-plus" aria-hidden="true"></i>
    </button>
  </div>
</template>
