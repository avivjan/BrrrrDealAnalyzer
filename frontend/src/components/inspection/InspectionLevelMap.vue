<script setup lang="ts">
/**
 * The level map: one tile per checklist section, each with a progress ring
 * and its items as chips. Tap any chip to jump to that card, so the
 * walkthrough can follow the house's layout instead of a fixed order.
 */
import {
  INSPECTION_CHECKLIST_CONFIG,
  itemStatusOf,
  levelProgress,
  type InspectionItemAnswers,
} from "../../inspection/inspectionChecklistLogic";
import { INSPECTION_STATUS_APPEARANCE } from "../../inspection/inspectionStatusAppearance";

defineProps<{ answersByItemKey: Record<string, InspectionItemAnswers>; celebratedSectionKey: string | null }>();
const emit = defineEmits<{ openItem: [itemKey: string] }>();
</script>

<template>
  <div class="grid gap-4 lg:grid-cols-2">
    <section
      v-for="(section, sectionIndex) in INSPECTION_CHECKLIST_CONFIG.sections"
      :key="section.key"
      :data-testid="`inspection.map.level.${section.key}`"
      class="relative overflow-hidden rounded-panel border border-line bg-surface p-5 shadow-2"
      :aria-labelledby="`inspection-level-${section.key}`"
    >
      <div class="flex items-center gap-4">
        <div class="relative" :class="celebratedSectionKey === section.key ? 'inspection-level-cleared' : ''">
          <UiProgressRing
            :value="levelProgress(section, answersByItemKey).checkedItemCount / levelProgress(section, answersByItemKey).totalItemCount"
            :label="`${levelProgress(section, answersByItemKey).checkedItemCount} of ${levelProgress(section, answersByItemKey).totalItemCount} checked`"
            :size="60"
            :thickness="6"
            :tone="levelProgress(section, answersByItemKey).isComplete ? 'positive' : 'primary'"
          />
          <span v-if="celebratedSectionKey === section.key" class="inspection-burst" aria-hidden="true">
            <i v-for="dot in 10" :key="dot" :style="{ '--burst-angle': `${dot * 36}deg` }"></i>
          </span>
        </div>
        <div class="min-w-0">
          <p class="text-xs font-medium uppercase tracking-[0.14em] text-fg-muted">Level {{ sectionIndex + 1 }}</p>
          <h2 :id="`inspection-level-${section.key}`" class="font-display text-2xl leading-tight text-fg">{{ section.label }}</h2>
          <p class="numeric text-sm text-fg-muted">
            {{ levelProgress(section, answersByItemKey).checkedItemCount }} / {{ levelProgress(section, answersByItemKey).totalItemCount }} checked
            <span v-if="levelProgress(section, answersByItemKey).isComplete" class="ml-1 font-semibold text-positive"><i class="pi pi-check text-xs" aria-hidden="true"></i> Cleared</span>
          </p>
        </div>
      </div>
      <ul role="list" class="mt-5 flex flex-wrap gap-2">
        <li v-for="item in section.items" :key="item.key">
          <button
            type="button"
            :data-testid="`inspection.map.item.${item.key}`"
            class="inspection-press flex min-h-12 items-center gap-2 rounded-full border-2 px-4 text-base font-medium transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            :class="INSPECTION_STATUS_APPEARANCE[itemStatusOf(item.key, answersByItemKey)].chipClass"
            @click="emit('openItem', item.key)"
          >
            <i :class="INSPECTION_STATUS_APPEARANCE[itemStatusOf(item.key, answersByItemKey)].icon" class="text-sm" aria-hidden="true"></i>
            <span class="text-fg">{{ item.label }}</span>
            <i v-if="item.is_critical && itemStatusOf(item.key, answersByItemKey) === 'not_checked'" class="pi pi-bolt text-xs text-accent" aria-label="Critical"></i>
            <span class="sr-only">: {{ INSPECTION_STATUS_APPEARANCE[itemStatusOf(item.key, answersByItemKey)].label }}</span>
          </button>
        </li>
      </ul>
    </section>
  </div>
</template>
