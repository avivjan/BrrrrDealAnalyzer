<script setup lang="ts">
/**
 * Link an inspection to a Bought Deal (logged-in users only; the parent sends
 * anonymous visitors to the login first). A searchable list of Bought Deals,
 * plus link and unlink. One inspection belongs to at most one deal.
 */
import { computed, onMounted, ref } from "vue";

import api from "../../api";
import { inspectionApi } from "../../api/inspection";
import { useInspectionStore } from "../../stores/inspectionStore";
import type { BoughtDealRes } from "../../types";
import type { LinkedBoughtDealRes } from "../../types/inspection";

const props = defineProps<{ inspectionId: string }>();
const emit = defineEmits<{ close: [] }>();

const store = useInspectionStore();
const boughtDeals = ref<BoughtDealRes[]>([]);
const linkedDeal = ref<LinkedBoughtDealRes | null>(null);
const searchText = ref("");
const isLoading = ref(true);
const busyDealId = ref<string | null>(null);
const errorMessage = ref<string | null>(null);

const dealTypeOf = (deal: BoughtDealRes): "BRRRR" | "FLIP" => (deal.deal_type === "FLIP" ? "FLIP" : "BRRRR");
const matchingDeals = computed(() => {
  const search = searchText.value.trim().toLowerCase();
  return boughtDeals.value.filter((deal) => !search || deal.address.toLowerCase().includes(search));
});

onMounted(async () => {
  try {
    const [deals, link] = await Promise.all([api.getBoughtDeals(), inspectionApi.getInspectionDealLink(props.inspectionId)]);
    boughtDeals.value = deals;
    linkedDeal.value = link.linked_deal;
  } catch {
    errorMessage.value = "Bought Deals could not be loaded. Are you signed in?";
  } finally {
    isLoading.value = false;
  }
});

async function link(deal: BoughtDealRes) {
  busyDealId.value = deal.id;
  errorMessage.value = null;
  try {
    linkedDeal.value = (await inspectionApi.linkInspectionToDeal(props.inspectionId, deal.id, dealTypeOf(deal))).linked_deal;
    await store.pollOtherDeviceChanges();
  } catch {
    errorMessage.value = "The inspection could not be linked. Try again.";
  } finally {
    busyDealId.value = null;
  }
}

async function unlink() {
  busyDealId.value = "unlink";
  errorMessage.value = null;
  try {
    linkedDeal.value = (await inspectionApi.unlinkInspectionFromDeal(props.inspectionId)).linked_deal;
    await store.pollOtherDeviceChanges();
  } catch {
    errorMessage.value = "The link could not be removed. Try again.";
  } finally {
    busyDealId.value = null;
  }
}
</script>

<template>
  <UiDrawer :open="true" size="md" data-testid="inspection.deal-link" @close="emit('close')">
    <template #header>Link to a Bought Deal</template>
    <div class="space-y-4">
      <div v-if="linkedDeal" class="rounded-card border border-positive/50 bg-positive/10 p-4" data-testid="inspection.deal-link.current">
        <p class="text-xs uppercase tracking-wide text-fg-muted">Linked to</p>
        <p class="mt-1 flex items-center gap-2 text-base font-semibold text-fg">
          <UiBadge :deal-type="linkedDeal.deal_type">{{ linkedDeal.deal_type }}</UiBadge>{{ linkedDeal.property_address || "A Bought Deal" }}
        </p>
        <UiButton class="mt-3" variant="secondary" data-testid="inspection.deal-link.unlink" :loading="busyDealId === 'unlink'" @click="unlink">
          <i class="pi pi-times mr-2" aria-hidden="true"></i>Unlink
        </UiButton>
      </div>
      <label class="block">
        <span class="sr-only">Search Bought Deals by address</span>
        <input v-model="searchText" data-testid="inspection.deal-link.search" type="search" placeholder="Search by address" class="ui-input min-h-12 w-full text-base" />
      </label>
      <p v-if="errorMessage" role="alert" class="text-sm text-negative">{{ errorMessage }}</p>
      <div v-if="isLoading" class="space-y-2"><UiSkeleton v-for="row in 3" :key="row" class="h-14 w-full" /></div>
      <p v-else-if="matchingDeals.length === 0" class="text-sm text-fg-muted">No Bought Deal matches.</p>
      <ul v-else role="list" class="space-y-2">
        <li v-for="deal in matchingDeals" :key="deal.id">
          <button
            type="button"
            :data-testid="`inspection.deal-link.deal.${deal.id}`"
            :disabled="busyDealId !== null || linkedDeal?.bought_deal_id === deal.id"
            class="flex min-h-14 w-full items-center gap-3 rounded-ctl border border-line bg-surface px-4 text-left text-base text-fg transition-colors duration-fast hover:border-fg-muted disabled:opacity-60"
            @click="link(deal)"
          >
            <UiBadge :deal-type="dealTypeOf(deal)">{{ dealTypeOf(deal) }}</UiBadge>
            <span class="min-w-0 flex-1 truncate">{{ deal.address }}</span>
            <i v-if="busyDealId === deal.id" class="pi pi-spinner pi-spin" aria-hidden="true"></i>
            <i v-else-if="linkedDeal?.bought_deal_id === deal.id" class="pi pi-check text-positive" aria-label="Linked"></i>
          </button>
        </li>
      </ul>
    </div>
  </UiDrawer>
</template>
