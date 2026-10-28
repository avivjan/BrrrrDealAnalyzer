<script setup lang="ts">
/**
 * The inspection summary (public): start info, then what to Replace and
 * Repair (with fields, notes and photos), then the windows to replace, then
 * the OK items folded away. "Share" sends a text summary and the link with
 * the Web Share API, or copies it where sharing is not available.
 */
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRouter } from "vue-router";

import "../inspection/inspectionMotion.css";
import InspectionPhotoLightbox from "../components/inspection/InspectionPhotoLightbox.vue";
import InspectionPhotoThumbnail from "../components/inspection/InspectionPhotoThumbnail.vue";
import InspectionReportDeliveryStatus from "../components/inspection/InspectionReportDeliveryStatus.vue";
import {
  WINDOWS_ITEM_KEY,
  WINDOWS_NEEDING_REPLACEMENT_FIELD_KEY,
  allChecklistItems,
  formatFieldValue,
  inspectionShareText,
  isFieldAnswered,
  itemStatusOf,
  visibleFieldsOfItem,
  type InspectionItemConfig,
  type InspectionItemStatus,
} from "../inspection/inspectionChecklistLogic";
import { INSPECTION_STATUS_APPEARANCE } from "../inspection/inspectionStatusAppearance";
import { useInspectionStore } from "../stores/inspectionStore";

const props = defineProps<{ inspectionId: string }>();
const router = useRouter();
const store = useInspectionStore();

watch(
  () => props.inspectionId,
  (inspectionId) => {
    if (store.inspection?.id !== inspectionId) void store.loadInspection(inspectionId);
  },
  { immediate: true },
);
// Right after a finish the report is still being sent: look again a few times until it settles.
const REPORT_STATUS_RECHECK_MILLISECONDS = 4000;
const MAXIMUM_REPORT_STATUS_RECHECKS = 8;
let reportStatusRecheckCount = 0;
const reportStatusRecheckTimer = setInterval(() => {
  if (store.inspection?.report_delivery_status !== "sending" || reportStatusRecheckCount >= MAXIMUM_REPORT_STATUS_RECHECKS) return;
  reportStatusRecheckCount += 1;
  void store.pollOtherDeviceChanges();
}, REPORT_STATUS_RECHECK_MILLISECONDS);
onBeforeUnmount(() => {
  clearInterval(reportStatusRecheckTimer);
  store.stopSyncing();
});

const itemsWithStatus = (status: InspectionItemStatus) => allChecklistItems().filter((item) => itemStatusOf(item.key, store.answersByItemKey) === status);
const replaceItems = computed(() => itemsWithStatus("replace"));
const repairItems = computed(() => itemsWithStatus("repair"));
const okItems = computed(() => itemsWithStatus("ok"));
const notCheckedItems = computed(() => itemsWithStatus("not_checked"));
const windowsToReplace = computed(() => Number(store.answersByItemKey[WINDOWS_ITEM_KEY]?.item_field_values?.[WINDOWS_NEEDING_REPLACEMENT_FIELD_KEY] ?? 0));
const isOkListOpen = ref(false);
const enlargedPhotoId = ref<string | null>(null);

function answeredFields(item: InspectionItemConfig) {
  const fieldValues = store.answersByItemKey[item.key]?.item_field_values ?? {};
  return visibleFieldsOfItem(item, fieldValues)
    .filter((field) => isFieldAnswered(field, fieldValues))
    .map((field) => ({ key: field.key, label: field.label, value: formatFieldValue(field, fieldValues[field.key]) }));
}
const photosOfItem = (itemKey: string) => store.photos.filter((photo) => photo.item_key === itemKey);

function formatInspectionDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  return year && month && day ? new Date(year, month - 1, day).toLocaleDateString("en-US", { weekday: "short", month: "long", day: "numeric", year: "numeric" }) : isoDate;
}

const shareFeedback = ref<string | null>(null);
async function share() {
  if (!store.inspection) return;
  const inspectionLink = `${window.location.origin}/inspections/${store.inspection.id}/summary`;
  const text = inspectionShareText(store.inspection, store.answersByItemKey, inspectionLink);
  const title = `Inspection: ${store.inspection.property_address}`;
  try {
    if (typeof navigator.share === "function") {
      await navigator.share({ title, text });
      return;
    }
    await navigator.clipboard.writeText(text);
    shareFeedback.value = "Summary copied. Paste it into a message.";
  } catch (error: any) {
    if (error?.name === "AbortError") return;
    shareFeedback.value = "Sharing is not available here. Copy the page link instead.";
  }
}
</script>

<template>
  <section class="mx-auto max-w-3xl px-4 py-6 sm:px-6" data-testid="inspection.summary">
    <div v-if="store.isLoading && !store.inspection" class="space-y-3"><UiSkeleton class="h-32 w-full" /><UiSkeleton class="h-64 w-full" /></div>
    <UiEmptyState v-else-if="store.loadErrorMessage" icon="pi pi-search">{{ store.loadErrorMessage }}</UiEmptyState>

    <template v-else-if="store.inspection">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <button type="button" class="min-h-11 text-sm text-fg-muted hover:text-fg" data-testid="inspection.summary.back" @click="router.push({ name: 'inspection-walkthrough', params: { inspectionId } })">
          <i class="pi pi-arrow-left mr-1" aria-hidden="true"></i>Back to the walkthrough
        </button>
        <UiButton size="lg" data-testid="inspection.summary.share" @click="share"><i class="pi pi-share-alt mr-2" aria-hidden="true"></i>Share</UiButton>
      </div>
      <p v-if="shareFeedback" role="status" class="mt-2 text-right text-sm text-fg-muted">{{ shareFeedback }}</p>

      <!-- Start info -->
      <header class="mt-4 rounded-panel border border-line bg-surface p-6 shadow-2">
        <p class="text-xs font-medium uppercase tracking-[0.14em] text-fg-muted">
          Inspection summary
          <span v-if="store.inspection.inspection_status === 'completed'" class="ml-2 text-positive"><i class="pi pi-check text-[10px]" aria-hidden="true"></i> Completed</span>
        </p>
        <h1 class="mt-2 font-display text-3xl leading-tight text-fg sm:text-4xl" data-testid="inspection.summary.address">{{ store.inspection.property_address }}</h1>
        <dl class="mt-4 grid gap-3 text-base sm:grid-cols-3">
          <div><dt class="text-sm text-fg-muted">Date</dt><dd class="text-fg">{{ formatInspectionDate(store.inspection.inspection_date) }}</dd></div>
          <div><dt class="text-sm text-fg-muted">Inspector</dt><dd class="text-fg">{{ store.inspection.inspector_name || "—" }}</dd></div>
          <div><dt class="text-sm text-fg-muted">Photos</dt><dd class="numeric text-fg">{{ store.photos.length }}</dd></div>
        </dl>
        <InspectionReportDeliveryStatus class="mt-4" :report-delivery-status="store.inspection.report_delivery_status" />
        <p v-if="store.inspection.completion_override_reason" class="mt-4 rounded-ctl border border-accent/50 bg-accent/10 p-3 text-sm text-fg" data-testid="inspection.summary.override">
          <i class="pi pi-bolt mr-1 text-accent" aria-hidden="true"></i>Finished before every mission: {{ store.inspection.completion_override_reason }}
        </p>
        <p v-if="notCheckedItems.length" class="mt-3 text-sm text-fg-muted">Not checked: {{ notCheckedItems.map((item) => item.label).join(", ") }}</p>
      </header>

      <!-- Replace, then Repair -->
      <section v-for="group in [{ status: 'replace' as const, items: replaceItems }, { status: 'repair' as const, items: repairItems }]" :key="group.status" class="mt-6" :data-testid="`inspection.summary.${group.status}`">
        <h2 class="flex items-center gap-2 font-display text-2xl" :class="INSPECTION_STATUS_APPEARANCE[group.status].textClass">
          <i :class="INSPECTION_STATUS_APPEARANCE[group.status].icon" aria-hidden="true"></i>{{ INSPECTION_STATUS_APPEARANCE[group.status].label }}
          <span class="numeric text-base text-fg-muted">({{ group.items.length }})</span>
        </h2>
        <p v-if="group.items.length === 0" class="mt-2 text-base text-fg-muted">Nothing marked {{ INSPECTION_STATUS_APPEARANCE[group.status].label }}.</p>
        <ul v-else role="list" class="mt-3 space-y-3">
          <li v-for="item in group.items" :key="item.key" class="rounded-card border bg-surface p-4" :class="INSPECTION_STATUS_APPEARANCE[group.status].chipClass">
            <h3 class="text-lg font-semibold text-fg">{{ item.label }}</h3>
            <dl v-if="answeredFields(item).length" class="mt-2 grid gap-x-4 gap-y-1 text-base sm:grid-cols-2">
              <div v-for="field in answeredFields(item)" :key="field.key" class="flex gap-2"><dt class="text-fg-muted">{{ field.label }}:</dt><dd class="font-medium text-fg">{{ field.value }}</dd></div>
            </dl>
            <p v-if="store.answersByItemKey[item.key]?.item_notes" class="mt-2 whitespace-pre-line text-base text-fg">{{ store.answersByItemKey[item.key]?.item_notes }}</p>
            <ul v-if="photosOfItem(item.key).length" role="list" class="mt-3 flex flex-wrap gap-2">
              <li v-for="photo in photosOfItem(item.key)" :key="photo.id">
                <button type="button" :aria-label="`Enlarge photo of ${item.label}`" class="block size-20 overflow-hidden rounded-ctl border border-line" @click="enlargedPhotoId = photo.id">
                  <InspectionPhotoThumbnail :inspection-id="inspectionId" :photo-id="photo.id" :alt="`Photo of ${item.label}`" />
                </button>
              </li>
            </ul>
          </li>
        </ul>
      </section>

      <!-- Windows -->
      <section class="mt-6 flex items-center justify-between rounded-card border border-line bg-surface p-4" data-testid="inspection.summary.windows">
        <h2 class="text-lg font-semibold text-fg"><i class="pi pi-th-large mr-2 text-fg-muted" aria-hidden="true"></i>Windows to replace</h2>
        <span class="numeric font-display text-3xl text-fg">{{ windowsToReplace }}</span>
      </section>

      <!-- OK, folded -->
      <section class="mt-6" data-testid="inspection.summary.ok">
        <button type="button" :aria-expanded="isOkListOpen" class="flex min-h-12 w-full items-center justify-between rounded-card border border-line bg-surface px-4 text-left" @click="isOkListOpen = !isOkListOpen">
          <span class="flex items-center gap-2 text-lg font-semibold text-positive"><i class="pi pi-check" aria-hidden="true"></i>OK <span class="numeric text-base text-fg-muted">({{ okItems.length }})</span></span>
          <i :class="isOkListOpen ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="text-fg-muted" aria-hidden="true"></i>
        </button>
        <ul v-if="isOkListOpen" role="list" class="inspection-fade-in mt-2 space-y-2">
          <li v-for="item in okItems" :key="item.key" class="rounded-ctl border border-line bg-surface px-4 py-3 text-base">
            <span class="font-medium text-fg">{{ item.label }}</span>
            <span v-if="answeredFields(item).length" class="text-fg-muted"> · {{ answeredFields(item).map((field) => `${field.label}: ${field.value}`).join(" · ") }}</span>
          </li>
        </ul>
      </section>

      <InspectionPhotoLightbox v-if="enlargedPhotoId" :inspection-id="inspectionId" :photo-id="enlargedPhotoId" alt="Inspection photo" :can-delete="false" @close="enlargedPhotoId = null" />
    </template>
  </section>
</template>
