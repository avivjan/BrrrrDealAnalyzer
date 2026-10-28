<script setup lang="ts">
/** One line under a finished inspection: was its report e-mailed and saved to Drive? */
import { computed } from "vue";

import type { PublicInspectionRes } from "../../types/inspection";

const props = defineProps<{ reportDeliveryStatus: PublicInspectionRes["report_delivery_status"] }>();

const APPEARANCE = {
  delivered: { icon: "pi pi-check-circle", toneClass: "text-positive", text: "Report e-mailed and saved to Drive" },
  sending: { icon: "pi pi-spinner pi-spin", toneClass: "text-fg-muted", text: "Sending the report…" },
  will_retry: { icon: "pi pi-clock", toneClass: "text-warning", text: "The report couldn't be sent yet; it will retry automatically" },
} as const;

const appearance = computed(() => (props.reportDeliveryStatus ? APPEARANCE[props.reportDeliveryStatus] : null));
</script>

<template>
  <p v-if="appearance" role="status" aria-live="polite" data-testid="inspection.report-status" :data-state="reportDeliveryStatus" class="flex items-center gap-2 text-sm" :class="appearance.toneClass">
    <i :class="appearance.icon" aria-hidden="true"></i>{{ appearance.text }}
  </p>
</template>
