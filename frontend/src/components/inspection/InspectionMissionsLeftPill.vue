<script setup lang="ts">
/**
 * "Missions left": the CRITICAL items still not checked, always in view.
 * Tap to see which; tap one to go to it. Turns into a green "All missions
 * done" once every expensive system has been checked.
 */
import { ref } from "vue";

import type { InspectionItemConfig } from "../../inspection/inspectionChecklistLogic";

defineProps<{ remainingCriticalItems: InspectionItemConfig[] }>();
const emit = defineEmits<{ openItem: [itemKey: string] }>();
const isListOpen = ref(false);
</script>

<template>
  <div class="relative">
    <button
      v-if="remainingCriticalItems.length > 0"
      type="button"
      data-testid="inspection.missions"
      :aria-expanded="isListOpen"
      class="inspection-press flex min-h-11 items-center gap-2 rounded-full border border-accent/60 bg-accent/15 px-4 text-sm font-semibold text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      @click="isListOpen = !isListOpen"
    >
      <i class="pi pi-bolt text-accent" aria-hidden="true"></i>
      <span class="numeric">{{ remainingCriticalItems.length }}</span>
      {{ remainingCriticalItems.length === 1 ? "mission left" : "missions left" }}
    </button>
    <span v-else data-testid="inspection.missions.done" class="flex min-h-11 items-center gap-2 rounded-full border border-positive/60 bg-positive/15 px-4 text-sm font-semibold text-positive">
      <i class="pi pi-verified" aria-hidden="true"></i>All missions done
    </span>
    <ul
      v-if="isListOpen && remainingCriticalItems.length > 0"
      role="list"
      data-testid="inspection.missions.list"
      class="inspection-fade-in absolute right-0 top-full z-30 mt-2 w-60 rounded-card border border-line bg-surface p-2 shadow-4"
    >
      <li v-for="item in remainingCriticalItems" :key="item.key">
        <button type="button" class="flex min-h-11 w-full items-center gap-2 rounded-ctl px-3 text-left text-base text-fg hover:bg-surface-2" @click="isListOpen = false; emit('openItem', item.key)">
          <i class="pi pi-bolt text-xs text-accent" aria-hidden="true"></i>{{ item.label }}
        </button>
      </li>
    </ul>
  </div>
</template>
