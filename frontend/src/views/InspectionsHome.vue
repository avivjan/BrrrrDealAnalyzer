<script setup lang="ts">
/**
 * The Inspections tab (public). Anyone sees "New inspection" and the
 * inspections opened on this device (there is deliberately no public list).
 * Logged-in users also see every inspection, and can delete one.
 */
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import "../inspection/inspectionMotion.css";
import { inspectionApi } from "../api/inspection";
import { forgetInspectionOnDevice, readRecentInspectionsOnDevice, type RecentInspectionOnDevice } from "../inspection/inspectionRecentOnDevice";
import { useAuthStore } from "../stores/authStore";
import type { InspectionListRowRes } from "../types/inspection";

const router = useRouter();
const auth = useAuthStore();

const recentInspectionsOnDevice = ref<RecentInspectionOnDevice[]>(readRecentInspectionsOnDevice());
const allInspections = ref<InspectionListRowRes[] | null>(null);
const isLoadingAllInspections = ref(false);
const listErrorMessage = ref<string | null>(null);
const inspectionIdAwaitingDeleteConfirmation = ref<string | null>(null);
const deletingInspectionId = ref<string | null>(null);

const isLoggedIn = computed(() => auth.status === "trusted" || auth.status === "off");

function formatInspectionDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  return year && month && day ? new Date(year, month - 1, day).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : isoDate;
}

async function loadAllInspections() {
  isLoadingAllInspections.value = true;
  listErrorMessage.value = null;
  try {
    allInspections.value = await inspectionApi.listInspections();
  } catch {
    allInspections.value = null;
    listErrorMessage.value = "The list of all inspections could not be loaded.";
  } finally {
    isLoadingAllInspections.value = false;
  }
}

async function deleteInspection(inspectionId: string) {
  deletingInspectionId.value = inspectionId;
  try {
    await inspectionApi.deleteInspection(inspectionId);
    allInspections.value = allInspections.value?.filter((row) => row.id !== inspectionId) ?? null;
    recentInspectionsOnDevice.value = forgetInspectionOnDevice(inspectionId);
  } catch {
    listErrorMessage.value = "The inspection could not be deleted.";
  } finally {
    deletingInspectionId.value = null;
    inspectionIdAwaitingDeleteConfirmation.value = null;
  }
}

function openInspection(inspectionId: string) {
  void router.push({ name: "inspection-walkthrough", params: { inspectionId } });
}

onMounted(async () => {
  if (auth.status === "unknown") await auth.load();
  if (isLoggedIn.value) await loadAllInspections();
});
</script>

<template>
  <section class="mx-auto max-w-5xl px-4 py-6 sm:px-6" data-testid="inspections.page">
    <div class="relative overflow-hidden rounded-panel border border-line bg-surface p-6 shadow-3 sm:p-8">
      <div aria-hidden="true" class="pointer-events-none absolute -right-16 -top-16 size-64 rounded-full bg-primary/10 blur-3xl"></div>
      <p class="text-xs font-medium uppercase tracking-[0.14em] text-fg-muted">Pre-purchase walkthrough</p>
      <h1 class="mt-2 font-display text-4xl leading-tight text-fg sm:text-5xl">Inspect a property</h1>
      <p class="mt-3 max-w-xl text-base text-fg-muted">
        Walk the house one card at a time. The expensive systems are your missions: the inspection can't finish until every one is checked.
      </p>
      <UiButton class="mt-6" size="lg" data-testid="inspections.new" @click="router.push({ name: 'inspection-new' })">
        <i class="pi pi-plus mr-2" aria-hidden="true"></i>New inspection
      </UiButton>
    </div>

    <div class="mt-8">
      <h2 class="font-display text-2xl text-fg">Recent on this device</h2>
      <p v-if="recentInspectionsOnDevice.length === 0" class="mt-2 text-base text-fg-muted" data-testid="inspections.recent.empty">
        Inspections you open on this device show up here. To reach one from another device, use its link.
      </p>
      <ul v-else role="list" class="mt-3 grid gap-3 sm:grid-cols-2" data-testid="inspections.recent">
        <li v-for="recent in recentInspectionsOnDevice" :key="recent.inspection_id">
          <button
            type="button"
            :data-testid="`inspections.recent.${recent.inspection_id}`"
            class="inspection-press flex min-h-16 w-full items-center gap-3 rounded-card border border-line bg-surface px-4 py-3 text-left transition-colors duration-fast hover:border-fg-muted"
            @click="openInspection(recent.inspection_id)"
          >
            <span class="grid size-10 shrink-0 place-items-center rounded-full bg-primary/10 text-primary"><i class="pi pi-home" aria-hidden="true"></i></span>
            <span class="min-w-0 flex-1">
              <span class="block truncate text-base font-semibold text-fg">{{ recent.property_address }}</span>
              <span class="block text-sm text-fg-muted">{{ formatInspectionDate(recent.inspection_date) }}</span>
            </span>
            <i class="pi pi-chevron-right text-fg-muted" aria-hidden="true"></i>
          </button>
        </li>
      </ul>
    </div>

    <div v-if="isLoggedIn" class="mt-10" data-testid="inspections.all">
      <h2 class="font-display text-2xl text-fg">All inspections</h2>
      <p v-if="listErrorMessage" role="alert" class="mt-2 text-sm text-negative">{{ listErrorMessage }}</p>
      <div v-if="isLoadingAllInspections" class="mt-3 space-y-2"><UiSkeleton v-for="row in 3" :key="row" class="h-16 w-full" /></div>
      <p v-else-if="allInspections && allInspections.length === 0" class="mt-2 text-base text-fg-muted">No inspections yet.</p>
      <ul v-else-if="allInspections" role="list" class="mt-3 divide-y divide-line overflow-hidden rounded-card border border-line bg-surface">
        <li v-for="row in allInspections" :key="row.id" class="flex flex-wrap items-center gap-3 px-4 py-3" :data-testid="`inspections.all.${row.id}`">
          <button type="button" class="min-h-11 min-w-0 flex-1 text-left" @click="openInspection(row.id)">
            <span class="block truncate text-base font-semibold text-fg">{{ row.property_address }}</span>
            <span class="flex flex-wrap items-center gap-x-3 text-sm text-fg-muted">
              <span>{{ formatInspectionDate(row.inspection_date) }}</span>
              <span class="numeric">{{ row.checked_item_count }}/{{ row.total_item_count }} checked</span>
              <span v-if="row.repair_or_replace_item_count" class="text-warning"><i class="pi pi-wrench text-xs" aria-hidden="true"></i> {{ row.repair_or_replace_item_count }} to fix</span>
              <span v-if="row.linked_deal"><i class="pi pi-link text-xs" aria-hidden="true"></i> {{ row.linked_deal.deal_board === "my_deals" ? "My Deals" : "Bought" }} · {{ row.linked_deal.property_address }}</span>
            </span>
          </button>
          <UiBadge :tone="row.inspection_status === 'completed' ? 'positive' : 'neutral'">{{ row.inspection_status === "completed" ? "Completed" : "Draft" }}</UiBadge>
          <template v-if="inspectionIdAwaitingDeleteConfirmation === row.id">
            <UiButton variant="danger" size="sm" :data-testid="`inspections.all.${row.id}.confirm-delete`" :loading="deletingInspectionId === row.id" @click="deleteInspection(row.id)">Delete</UiButton>
            <UiButton variant="ghost" size="sm" @click="inspectionIdAwaitingDeleteConfirmation = null">Cancel</UiButton>
          </template>
          <UiIconButton v-else size="md" label="Delete inspection" :data-testid="`inspections.all.${row.id}.delete`" @click="inspectionIdAwaitingDeleteConfirmation = row.id">
            <i class="pi pi-trash" aria-hidden="true"></i>
          </UiIconButton>
        </li>
      </ul>
    </div>
  </section>
</template>
