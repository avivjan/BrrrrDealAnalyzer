<script setup lang="ts">
/** The finish screen: a short, full-screen moment with the inspection's numbers, then the summary. */
import type { PublicInspectionRes } from "../../types/inspection";
import InspectionReportDeliveryStatus from "./InspectionReportDeliveryStatus.vue";

defineProps<{
  checkedItemCount: number;
  totalItemCount: number;
  repairItemCount: number;
  replaceItemCount: number;
  photoCount: number;
  reportDeliveryStatus: PublicInspectionRes["report_delivery_status"];
}>();
const emit = defineEmits<{ viewSummary: [] }>();
</script>

<template>
  <Teleport to="body">
    <div role="dialog" aria-modal="true" aria-labelledby="inspection-finished-title" data-testid="inspection.finished" class="inspection-fade-in fixed inset-0 z-[850] grid place-items-center bg-page/95 p-6 backdrop-blur-glass">
      <div class="inspection-finish-rise w-full max-w-lg text-center">
        <div class="relative mx-auto mb-6 grid size-28 place-items-center rounded-full bg-positive/15 text-positive inspection-level-cleared">
          <i class="pi pi-verified text-6xl" aria-hidden="true"></i>
          <span class="inspection-burst" aria-hidden="true"><i v-for="dot in 10" :key="dot" :style="{ '--burst-angle': `${dot * 36}deg` }"></i></span>
        </div>
        <h2 id="inspection-finished-title" class="font-display text-4xl text-fg">Inspection complete</h2>
        <p class="mt-2 text-base text-fg-muted">Every answer is saved. Share the summary with your contractor or partner.</p>
        <InspectionReportDeliveryStatus class="mt-3 justify-center" :report-delivery-status="reportDeliveryStatus" />
        <dl class="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div class="rounded-card border border-line bg-surface p-3">
            <dt class="text-xs uppercase tracking-wide text-fg-muted">Checked</dt>
            <dd class="numeric mt-1 font-display text-3xl text-fg">{{ checkedItemCount }}/{{ totalItemCount }}</dd>
          </div>
          <div class="rounded-card border border-line bg-surface p-3">
            <dt class="text-xs uppercase tracking-wide text-fg-muted">Repair</dt>
            <dd class="numeric mt-1 font-display text-3xl text-warning">{{ repairItemCount }}</dd>
          </div>
          <div class="rounded-card border border-line bg-surface p-3">
            <dt class="text-xs uppercase tracking-wide text-fg-muted">Replace</dt>
            <dd class="numeric mt-1 font-display text-3xl text-negative">{{ replaceItemCount }}</dd>
          </div>
          <div class="rounded-card border border-line bg-surface p-3">
            <dt class="text-xs uppercase tracking-wide text-fg-muted">Photos</dt>
            <dd class="numeric mt-1 font-display text-3xl text-fg">{{ photoCount }}</dd>
          </div>
        </dl>
        <UiButton class="mt-8" size="lg" block data-testid="inspection.finished.summary" @click="emit('viewSummary')">
          View summary <i class="pi pi-arrow-right ml-2" aria-hidden="true"></i>
        </UiButton>
      </div>
    </div>
  </Teleport>
</template>
