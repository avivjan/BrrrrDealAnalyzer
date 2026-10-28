<script setup lang="ts">
/**
 * On a deal's window (My Deals or Bought Deals, logged in): the inspections
 * linked to it, with status, date and how many items need Repair or Replace,
 * plus "New inspection", which starts one already linked, with the deal's
 * address prefilled. Moving a My Deals deal to Bought carries them along.
 */
import { onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { inspectionApi } from "../../api/inspection";
import { rememberInspectionOnDevice } from "../../inspection/inspectionRecentOnDevice";
import type { InspectionDealBoard, InspectionListRowRes } from "../../types/inspection";

const props = defineProps<{
  dealBoard: InspectionDealBoard;
  dealId: string;
  dealType: "BRRRR" | "FLIP";
  /** The hook prefix of the window it sits in, e.g. "boughtdeals.modal" or "mydeals.modal". */
  testIdPrefix: string;
}>();
const router = useRouter();

const linkedInspections = ref<InspectionListRowRes[]>([]);
const isLoading = ref(true);
const isCreating = ref(false);
const errorMessage = ref<string | null>(null);

async function loadLinkedInspections() {
  isLoading.value = true;
  errorMessage.value = null;
  try {
    linkedInspections.value = await inspectionApi.listDealInspections(props.dealBoard, props.dealId, props.dealType);
  } catch {
    errorMessage.value = "Inspections could not be loaded.";
  } finally {
    isLoading.value = false;
  }
}

async function startLinkedInspection() {
  isCreating.value = true;
  errorMessage.value = null;
  try {
    const inspection = await inspectionApi.createInspectionForDeal(props.dealBoard, props.dealId, props.dealType);
    rememberInspectionOnDevice({ inspection_id: inspection.id, property_address: inspection.property_address, inspection_date: inspection.inspection_date });
    await router.push({ name: "inspection-walkthrough", params: { inspectionId: inspection.id } });
  } catch {
    errorMessage.value = "The inspection could not be started.";
  } finally {
    isCreating.value = false;
  }
}

function formatInspectionDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  return year && month && day ? new Date(year, month - 1, day).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : isoDate;
}

onMounted(loadLinkedInspections);
watch(() => props.dealId, loadLinkedInspections);
</script>

<template>
  <UiCard tone="muted" class="mb-6" :data-testid="`${testIdPrefix}.inspections`">
    <UiSectionHeader as="h4" class="mb-3">
      Inspections
      <template #actions>
        <UiButton size="sm" variant="secondary" :data-testid="`${testIdPrefix}.inspections.new`" :loading="isCreating" @click="startLinkedInspection">
          <i class="pi pi-plus mr-1" aria-hidden="true"></i>New inspection
        </UiButton>
      </template>
    </UiSectionHeader>
    <p v-if="errorMessage" role="alert" class="text-sm text-negative">{{ errorMessage }}</p>
    <UiSkeleton v-if="isLoading" class="h-12 w-full" />
    <p v-else-if="linkedInspections.length === 0" class="text-sm text-fg-muted">No inspection linked yet.</p>
    <ul v-else role="list" class="space-y-2">
      <li v-for="inspection in linkedInspections" :key="inspection.id">
        <RouterLink
          :to="{ name: 'inspection-walkthrough', params: { inspectionId: inspection.id } }"
          :data-testid="`${testIdPrefix}.inspections.${inspection.id}`"
          class="flex min-h-12 flex-wrap items-center gap-x-3 gap-y-1 rounded-ctl border border-line bg-surface px-3 py-2 text-sm hover:border-fg-muted"
        >
          <UiBadge :tone="inspection.inspection_status === 'completed' ? 'positive' : 'neutral'">{{ inspection.inspection_status === "completed" ? "Completed" : "Draft" }}</UiBadge>
          <span class="text-fg">{{ formatInspectionDate(inspection.inspection_date) }}</span>
          <span class="numeric text-fg-muted">{{ inspection.checked_item_count }}/{{ inspection.total_item_count }} checked</span>
          <span class="ml-auto font-medium" :class="inspection.repair_or_replace_item_count ? 'text-warning' : 'text-fg-muted'">
            <i class="pi pi-wrench text-xs" aria-hidden="true"></i> {{ inspection.repair_or_replace_item_count }} Repair/Replace
          </span>
        </RouterLink>
      </li>
    </ul>
  </UiCard>
</template>
