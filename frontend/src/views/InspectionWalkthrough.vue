<script setup lang="ts">
/**
 * The inspection walkthrough (public: anyone with the link).
 *
 * Without an item in the URL it shows the level map; with one
 * (`/inspections/:id/items/:itemKey`) it shows that item's card. Cards move
 * with a swipe or the big ◀ ▶ buttons. The sticky header keeps the overall
 * progress, the "missions left" (CRITICAL items still unchecked), the save
 * state and Finish in view at all times.
 */
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRouter } from "vue-router";

import "../inspection/inspectionMotion.css";
import InspectionDealLinkDrawer from "../components/inspection/InspectionDealLinkDrawer.vue";
import InspectionFinishCelebration from "../components/inspection/InspectionFinishCelebration.vue";
import InspectionFinishDialog from "../components/inspection/InspectionFinishDialog.vue";
import InspectionItemCard from "../components/inspection/InspectionItemCard.vue";
import InspectionLevelMap from "../components/inspection/InspectionLevelMap.vue";
import InspectionMissionsLeftPill from "../components/inspection/InspectionMissionsLeftPill.vue";
import InspectionSaveIndicator from "../components/inspection/InspectionSaveIndicator.vue";
import {
  INSPECTION_CHECKLIST_CONFIG,
  allChecklistItems,
  findChecklistItem,
  finishEligibility,
  itemStatusOf,
  levelProgress,
  neighbourItemKey,
  overallProgressFraction,
  remainingCriticalItems,
  sectionOfItem,
} from "../inspection/inspectionChecklistLogic";
import { useAuthStore } from "../stores/authStore";
import { useInspectionStore } from "../stores/inspectionStore";

const props = defineProps<{ inspectionId: string; itemKey?: string }>();

const router = useRouter();
const store = useInspectionStore();
const auth = useAuthStore();

watch(
  () => props.inspectionId,
  (inspectionId) => void store.loadInspection(inspectionId),
  { immediate: true },
);
onBeforeUnmount(() => {
  store.stopSyncing();
  void store.flushPendingChanges();
});

const currentItem = computed(() => (props.itemKey ? findChecklistItem(props.itemKey) : undefined));
const currentSection = computed(() => (props.itemKey ? sectionOfItem(props.itemKey) : undefined));
const missionsLeft = computed(() => remainingCriticalItems(store.answersByItemKey));
const progressPercent = computed(() => Math.round(overallProgressFraction(store.answersByItemKey) * 100));
const checkedItemCount = computed(() => allChecklistItems().filter((item) => itemStatusOf(item.key, store.answersByItemKey) !== "not_checked").length);
const totalItemCount = allChecklistItems().length;
const itemPosition = computed(() => (props.itemKey ? allChecklistItems().findIndex((item) => item.key === props.itemKey) + 1 : 0));
const isCompleted = computed(() => store.inspection?.inspection_status === "completed");

// --- navigation between cards -------------------------------------------
const cardDirection = ref<"forward" | "backward">("forward");

function openItem(itemKey: string) {
  cardDirection.value = "forward";
  void router.push({ name: "inspection-item", params: { inspectionId: props.inspectionId, itemKey } });
}

function openMap() {
  void router.push({ name: "inspection-walkthrough", params: { inspectionId: props.inspectionId } });
}

function goToNeighbour(direction: 1 | -1) {
  if (!props.itemKey) return;
  const neighbour = neighbourItemKey(props.itemKey, direction);
  cardDirection.value = direction === 1 ? "forward" : "backward";
  if (neighbour) void router.replace({ name: "inspection-item", params: { inspectionId: props.inspectionId, itemKey: neighbour } });
  else openMap();
}

const SWIPE_MINIMUM_DISTANCE_PIXELS = 60;
let swipeStart: { x: number; y: number } | null = null;
function onPointerDown(event: PointerEvent) {
  const target = event.target as HTMLElement;
  swipeStart = target.closest("input, textarea, button, select") ? null : { x: event.clientX, y: event.clientY };
}
function onPointerUp(event: PointerEvent) {
  if (!swipeStart) return;
  const horizontalDistance = event.clientX - swipeStart.x;
  const verticalDistance = event.clientY - swipeStart.y;
  swipeStart = null;
  if (Math.abs(horizontalDistance) < SWIPE_MINIMUM_DISTANCE_PIXELS || Math.abs(horizontalDistance) < Math.abs(verticalDistance) * 1.5) return;
  goToNeighbour(horizontalDistance < 0 ? 1 : -1);
}

// --- level cleared celebration ------------------------------------------
const celebratedSectionKey = ref<string | null>(null);
const levelClearedToast = ref<string | null>(null);
let celebrationTimer: ReturnType<typeof setTimeout> | null = null;
const completeSectionKeys = computed(() =>
  INSPECTION_CHECKLIST_CONFIG.sections.filter((section) => levelProgress(section, store.answersByItemKey).isComplete).map((section) => section.key),
);
watch(completeSectionKeys, (nowComplete, previouslyComplete) => {
  if (store.isLoading || !previouslyComplete) return;
  const newlyCleared = nowComplete.find((sectionKey) => !previouslyComplete.includes(sectionKey));
  if (!newlyCleared) return;
  celebratedSectionKey.value = newlyCleared;
  levelClearedToast.value = `Level cleared: ${INSPECTION_CHECKLIST_CONFIG.sections.find((section) => section.key === newlyCleared)?.label}`;
  if (celebrationTimer) clearTimeout(celebrationTimer);
  celebrationTimer = setTimeout(() => {
    celebratedSectionKey.value = null;
    levelClearedToast.value = null;
  }, 2600);
});

// --- finishing -------------------------------------------------------------
const isFinishDialogOpen = ref(false);
const isFinishing = ref(false);
const finishErrorMessage = ref<string | null>(null);
const showFinishCelebration = ref(false);
const eligibility = computed(() => finishEligibility(store.answersByItemKey));

async function finish(completionOverrideReason: string | null) {
  isFinishing.value = true;
  finishErrorMessage.value = null;
  try {
    await store.completeInspection(completionOverrideReason);
    isFinishDialogOpen.value = false;
    showFinishCelebration.value = true;
  } catch (error: any) {
    const detail = error?.response?.data?.detail;
    finishErrorMessage.value = typeof detail === "string" ? detail : detail?.message ?? error?.message ?? "The inspection could not be finished.";
  } finally {
    isFinishing.value = false;
  }
}

function onFinishPressed() {
  if (eligibility.value.canFinish) void finish(null);
  else isFinishDialogOpen.value = true;
}

const summaryCounts = computed(() => {
  const statuses = allChecklistItems().map((item) => itemStatusOf(item.key, store.answersByItemKey));
  return {
    repair: statuses.filter((status) => status === "repair").length,
    replace: statuses.filter((status) => status === "replace").length,
  };
});

// --- link to a Bought Deal (login required) ---------------------------------
const isDealLinkDrawerOpen = ref(false);
async function onLinkToDealPressed() {
  const status = auth.status === "unknown" ? await auth.load() : auth.status;
  if (status === "anon" || status === "pending") {
    void router.push({ name: "login", query: { next: router.currentRoute.value.fullPath } });
    return;
  }
  isDealLinkDrawerOpen.value = true;
}
</script>

<template>
  <div class="flex min-h-full flex-col" data-testid="inspection.page">
    <div v-if="store.isLoading && !store.inspection" class="mx-auto max-w-3xl space-y-4 p-4 sm:p-6">
      <UiSkeleton class="h-24 w-full" />
      <UiSkeleton class="h-64 w-full" />
    </div>

    <div v-else-if="store.loadErrorMessage" class="mx-auto max-w-xl p-6">
      <UiEmptyState icon="pi pi-search" data-testid="inspection.load-error">
        <p class="text-base">{{ store.loadErrorMessage }}</p>
        <RouterLink to="/inspections" class="mt-4 inline-flex min-h-11 items-center text-primary underline-offset-4 hover:underline">Back to inspections</RouterLink>
      </UiEmptyState>
    </div>

    <template v-else-if="store.inspection">
      <!-- Sticky header: progress, missions left, save state -->
      <header class="sticky top-0 z-20 border-b border-line bg-page px-4 pb-3 pt-3 sm:px-6">
        <div class="mx-auto flex max-w-5xl flex-wrap items-center gap-x-4 gap-y-2">
          <button type="button" class="min-w-0 basis-full text-left sm:basis-auto sm:flex-1" data-testid="inspection.header.map" @click="openMap">
            <p class="text-xs font-medium uppercase tracking-[0.14em] text-fg-muted">
              Inspection<span v-if="isCompleted" class="ml-2 text-positive"><i class="pi pi-check text-[10px]" aria-hidden="true"></i> Completed</span>
            </p>
            <p class="truncate font-display text-xl text-fg sm:text-2xl" data-testid="inspection.header.address">{{ store.inspection.property_address }}</p>
          </button>
          <InspectionSaveIndicator :save-state="store.saveState" :pending-change-count="store.pendingChangeCount" :error-message="store.saveErrorMessage" />
          <InspectionMissionsLeftPill class="ml-auto" :remaining-critical-items="missionsLeft" @open-item="openItem" />
        </div>
        <div class="mx-auto mt-3 flex max-w-5xl items-center gap-3">
          <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2" role="progressbar" :aria-valuenow="progressPercent" aria-valuemin="0" aria-valuemax="100" aria-label="Inspection progress">
            <div class="inspection-progress-fill h-full rounded-full bg-primary" :style="{ width: `${progressPercent}%` }"></div>
          </div>
          <span class="numeric text-xs text-fg-muted" data-testid="inspection.header.progress">{{ checkedItemCount }}/{{ totalItemCount }}</span>
        </div>
      </header>

      <div class="mx-auto w-full max-w-5xl flex-1 px-4 pb-6 pt-5 sm:px-6">
        <!-- Level map -->
        <template v-if="!currentItem">
          <div class="mb-5 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 class="font-display text-3xl text-fg">Choose your next stop</h1>
              <p class="text-base text-fg-muted">Follow the house in any order. Tap an item to inspect it.</p>
            </div>
            <div class="flex flex-wrap gap-2">
              <UiButton variant="secondary" data-testid="inspection.link-deal" @click="onLinkToDealPressed">
                <i class="pi pi-link mr-2" aria-hidden="true"></i>{{ store.inspection.linked ? "Linked to a deal" : "Link to deal" }}
              </UiButton>
              <UiButton variant="secondary" data-testid="inspection.summary-link" @click="router.push({ name: 'inspection-summary', params: { inspectionId } })">
                <i class="pi pi-list mr-2" aria-hidden="true"></i>Summary
              </UiButton>
            </div>
          </div>
          <InspectionLevelMap :answers-by-item-key="store.answersByItemKey" :celebrated-section-key="celebratedSectionKey" @open-item="openItem" />
          <div class="mt-6">
            <UiButton
              size="lg"
              block
              data-testid="inspection.finish"
              :variant="eligibility.canFinish ? 'primary' : 'secondary'"
              :loading="isFinishing"
              @click="onFinishPressed"
            >
              <i class="pi pi-flag-fill mr-2" aria-hidden="true"></i>
              {{ isCompleted ? "Finish again" : "Finish inspection" }}
            </UiButton>
            <p v-if="!eligibility.canFinish" class="mt-2 text-center text-sm text-fg-muted" data-testid="inspection.finish.blocked">
              {{ eligibility.remainingCriticalItemLabels.length }} {{ eligibility.remainingCriticalItemLabels.length === 1 ? "mission" : "missions" }} left:
              {{ eligibility.remainingCriticalItemLabels.join(", ") }}
            </p>
            <p v-if="finishErrorMessage && !isFinishDialogOpen" role="alert" class="mt-2 text-center text-sm text-negative">{{ finishErrorMessage }}</p>
          </div>
        </template>

        <!-- One item card -->
        <template v-else>
          <div class="mx-auto max-w-2xl touch-pan-y" data-testid="inspection.card-area" @pointerdown="onPointerDown" @pointerup="onPointerUp" @pointercancel="swipeStart = null">
            <p class="numeric mb-3 text-center text-xs text-fg-muted">Item {{ itemPosition }} of {{ totalItemCount }}</p>
            <!-- A CSS-only entrance: nothing waits on it, so a card change is never held back. -->
            <div :key="currentItem.key" :class="`inspection-card-enter-${cardDirection}`">
              <InspectionItemCard :item="currentItem" :level-label="currentSection?.label ?? ''" />
            </div>
          </div>
        </template>
      </div>

      <!-- Bottom bar for cards: previous, map, next -->
      <nav
        v-if="currentItem"
        aria-label="Inspection items"
        class="sticky bottom-0 z-30 mt-6 border-t border-line bg-page px-4 pt-2"
        data-testid="inspection.card-nav"
      >
        <div class="mx-auto flex max-w-2xl items-center gap-3 pb-2">
          <button type="button" data-testid="inspection.card.previous" aria-label="Previous item" class="inspection-press grid size-14 shrink-0 place-items-center rounded-full border border-line bg-surface text-xl text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" @click="goToNeighbour(-1)">
            <i class="pi pi-chevron-left" aria-hidden="true"></i>
          </button>
          <button type="button" data-testid="inspection.card.map" class="inspection-press flex min-h-14 flex-1 items-center justify-center gap-2 rounded-full border border-line bg-surface text-base font-medium text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" @click="openMap">
            <i class="pi pi-map" aria-hidden="true"></i>Level map
          </button>
          <button type="button" data-testid="inspection.card.next" aria-label="Next item" class="inspection-press grid size-14 shrink-0 place-items-center rounded-full bg-primary text-xl text-primary-fg shadow-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" @click="goToNeighbour(1)">
            <i class="pi pi-chevron-right" aria-hidden="true"></i>
          </button>
        </div>
      </nav>

      <!-- Level cleared toast -->
      <div v-if="levelClearedToast" role="status" aria-live="polite" data-testid="inspection.level-cleared" class="inspection-finish-rise fixed inset-x-0 top-24 z-40 mx-auto w-fit rounded-full border border-positive/60 bg-surface px-5 py-3 text-base font-semibold text-positive shadow-4">
        <i class="pi pi-star-fill mr-2" aria-hidden="true"></i>{{ levelClearedToast }}
      </div>

      <InspectionFinishDialog
        v-if="isFinishDialogOpen && !eligibility.canFinish"
        :remaining-critical-item-labels="eligibility.remainingCriticalItemLabels"
        :is-submitting="isFinishing"
        :error-message="finishErrorMessage"
        @cancel="isFinishDialogOpen = false"
        @confirm="finish"
      />
      <InspectionFinishCelebration
        v-if="showFinishCelebration"
        :checked-item-count="checkedItemCount"
        :total-item-count="totalItemCount"
        :repair-item-count="summaryCounts.repair"
        :replace-item-count="summaryCounts.replace"
        :photo-count="store.photos.length"
        :report-delivery-status="store.inspection.report_delivery_status"
        @view-summary="router.push({ name: 'inspection-summary', params: { inspectionId } })"
      />
      <InspectionDealLinkDrawer v-if="isDealLinkDrawerOpen" :inspection-id="inspectionId" @close="isDealLinkDrawerOpen = false" />
    </template>
  </div>
</template>
