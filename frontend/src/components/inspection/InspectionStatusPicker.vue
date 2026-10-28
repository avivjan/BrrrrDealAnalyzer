<script setup lang="ts">
/**
 * The first question of every card: OK, Repair or Replace, as three big
 * buttons (one tap). "Not checked" is the default and can be restored with
 * the small reset link, for a mis-tap.
 */
import type { InspectionItemStatus } from "../../inspection/inspectionChecklistLogic";
import { CHOOSABLE_ITEM_STATUSES, INSPECTION_STATUS_APPEARANCE } from "../../inspection/inspectionStatusAppearance";

defineProps<{ modelValue: InspectionItemStatus }>();
const emit = defineEmits<{ "update:modelValue": [status: InspectionItemStatus] }>();
</script>

<template>
  <div>
    <div role="radiogroup" aria-label="Condition" class="grid grid-cols-3 gap-2 sm:gap-3">
      <button
        v-for="status in CHOOSABLE_ITEM_STATUSES"
        :key="status"
        type="button"
        role="radio"
        :aria-checked="modelValue === status"
        :data-testid="`inspection.card.status.${status}`"
        class="inspection-press flex min-h-16 flex-col items-center justify-center gap-1 rounded-card border-2 px-2 py-3 text-base font-semibold transition-[background-color,border-color,color,transform] duration-fast ease-standard focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        :class="modelValue === status ? INSPECTION_STATUS_APPEARANCE[status].selectedClass : 'border-line bg-surface text-fg hover:border-fg-muted'"
        @click="emit('update:modelValue', status)"
      >
        <i :class="[INSPECTION_STATUS_APPEARANCE[status].icon, 'text-xl', modelValue === status ? '' : INSPECTION_STATUS_APPEARANCE[status].textClass]" aria-hidden="true"></i>
        {{ INSPECTION_STATUS_APPEARANCE[status].label }}
      </button>
    </div>
    <button
      v-if="modelValue !== 'not_checked'"
      type="button"
      data-testid="inspection.card.status.reset"
      class="mt-2 min-h-11 px-1 text-sm text-fg-muted underline-offset-4 hover:underline"
      @click="emit('update:modelValue', 'not_checked')"
    >
      Mark as not checked
    </button>
  </div>
</template>
