<script setup lang="ts">
/**
 * The one "Liquidity timeline updated" notice (tasks/todo/ConstructionAccountPerRehab.md): several confirms in a row
 * update it in place ("3 edits · 5 rows") instead of stacking notices. A link opens the timeline.
 */
import { useLiquidityTimelineChangePromptStore } from '../../stores/liquidityTimelineChangePromptStore'

const promptStore = useLiquidityTimelineChangePromptStore()
</script>

<template>
  <div class="pointer-events-none fixed inset-x-0 bottom-20 z-[55] flex justify-center px-4 lg:bottom-6" aria-live="polite">
    <div v-if="promptStore.notice" data-testid="timeline-notice" role="status"
         class="pointer-events-auto flex items-center gap-3 rounded-full border-ui border-line bg-surface px-4 py-2 text-sm text-fg shadow-3">
      <i class="pi pi-check-circle text-positive" aria-hidden="true"></i>
      <span data-testid="timeline-notice.message">{{ promptStore.notice.message }}</span>
      <RouterLink v-if="promptStore.notice.rowCount" data-testid="timeline-notice.open-timeline" to="/liquidity" class="font-medium text-primary underline-offset-2 hover:underline">
        View timeline
      </RouterLink>
      <UiIconButton data-testid="timeline-notice.dismiss" label="Dismiss" size="sm" @click="promptStore.dismissNotice()">
        <i class="pi pi-times text-xs" aria-hidden="true"></i>
      </UiIconButton>
    </div>
  </div>
</template>
