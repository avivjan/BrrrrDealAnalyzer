<script setup lang="ts">
/**
 * Link an inspection to a deal (logged-in users only; the parent sends
 * anonymous visitors to the login first). A My Deals / Bought switch, a
 * searchable list of that board's deals, plus link and unlink. One inspection
 * belongs to at most one deal; moving a My Deals deal to Bought carries it.
 */
import { computed, onMounted, ref, watch } from "vue";

import api from "../../api";
import { inspectionApi } from "../../api/inspection";
import { useInspectionStore } from "../../stores/inspectionStore";
import type { InspectionDealBoard, LinkedDealRes } from "../../types/inspection";

const props = defineProps<{ inspectionId: string }>();
const emit = defineEmits<{ close: [] }>();

interface PickableDeal {
  id: string;
  address: string;
  deal_type: "BRRRR" | "FLIP";
}

const BOARD_OPTIONS = [
  { value: "my_deals", label: "My Deals" },
  { value: "bought", label: "Bought" },
];
const BOARD_LABELS: Record<InspectionDealBoard, string> = { my_deals: "My Deals", bought: "Bought Deals" };

const store = useInspectionStore();
const chosenBoard = ref<InspectionDealBoard>("my_deals");
const dealsByBoard = ref<Partial<Record<InspectionDealBoard, PickableDeal[]>>>({});
const linkedDeal = ref<LinkedDealRes | null>(null);
const searchText = ref("");
const isLoading = ref(true);
const busyDealId = ref<string | null>(null);
const errorMessage = ref<string | null>(null);

const asPickableDeal = (deal: { id: string; address: string; deal_type?: string }): PickableDeal => ({
  id: deal.id,
  address: deal.address,
  deal_type: deal.deal_type === "FLIP" ? "FLIP" : "BRRRR",
});

const matchingDeals = computed(() => {
  const search = searchText.value.trim().toLowerCase();
  return (dealsByBoard.value[chosenBoard.value] ?? []).filter((deal) => !search || deal.address.toLowerCase().includes(search));
});
const isLinkedTo = (deal: PickableDeal) => linkedDeal.value?.deal_board === chosenBoard.value && linkedDeal.value.deal_id === deal.id;

/** One request per board, shared by every caller (opening on the linked board and the switch both ask). */
const boardLoadRequests: Partial<Record<InspectionDealBoard, Promise<void>>> = {};

function loadBoard(board: InspectionDealBoard): Promise<void> {
  boardLoadRequests[board] ??= (async () => {
    isLoading.value = true;
    errorMessage.value = null;
    try {
      const deals = board === "my_deals" ? await api.getActiveDeals() : await api.getBoughtDeals();
      dealsByBoard.value = { ...dealsByBoard.value, [board]: deals.map(asPickableDeal) };
    } catch {
      delete boardLoadRequests[board];
      errorMessage.value = `${BOARD_LABELS[board]} could not be loaded. Are you signed in?`;
    } finally {
      isLoading.value = false;
    }
  })();
  return boardLoadRequests[board]!;
}

function chooseBoard(board: string) {
  chosenBoard.value = board === "bought" ? "bought" : "my_deals";
}

watch(chosenBoard, (board) => void loadBoard(board));

onMounted(async () => {
  try {
    linkedDeal.value = (await inspectionApi.getInspectionDealLink(props.inspectionId)).linked_deal;
    if (linkedDeal.value) chosenBoard.value = linkedDeal.value.deal_board;
  } catch {
    errorMessage.value = "The current link could not be loaded. Are you signed in?";
  }
  await loadBoard(chosenBoard.value);
});

async function link(deal: PickableDeal) {
  busyDealId.value = deal.id;
  errorMessage.value = null;
  try {
    linkedDeal.value = (await inspectionApi.linkInspectionToDeal(props.inspectionId, chosenBoard.value, deal.id, deal.deal_type)).linked_deal;
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
    <template #header>Link to a deal</template>
    <div class="space-y-4">
      <div v-if="linkedDeal" class="rounded-card border border-positive/50 bg-positive/10 p-4" data-testid="inspection.deal-link.current">
        <p class="text-xs uppercase tracking-wide text-fg-muted">Linked to · {{ BOARD_LABELS[linkedDeal.deal_board] }}</p>
        <p class="mt-1 flex items-center gap-2 text-base font-semibold text-fg">
          <UiBadge :deal-type="linkedDeal.deal_type">{{ linkedDeal.deal_type }}</UiBadge>{{ linkedDeal.property_address || "A deal" }}
        </p>
        <UiButton class="mt-3" variant="secondary" data-testid="inspection.deal-link.unlink" :loading="busyDealId === 'unlink'" @click="unlink">
          <i class="pi pi-times mr-2" aria-hidden="true"></i>Unlink
        </UiButton>
      </div>
      <UiSegmented :model-value="chosenBoard" :options="BOARD_OPTIONS" ariaLabel="Which deals" size="md" block data-testid="inspection.deal-link.board" @update:model-value="chooseBoard" />
      <label class="block">
        <span class="sr-only">Search {{ BOARD_LABELS[chosenBoard] }} by address</span>
        <input v-model="searchText" data-testid="inspection.deal-link.search" type="search" placeholder="Search by address" class="ui-input min-h-12 w-full text-base" />
      </label>
      <p v-if="errorMessage" role="alert" class="text-sm text-negative">{{ errorMessage }}</p>
      <div v-if="isLoading" class="space-y-2"><UiSkeleton v-for="row in 3" :key="row" class="h-14 w-full" /></div>
      <p v-else-if="matchingDeals.length === 0" class="text-sm text-fg-muted">No deal on {{ BOARD_LABELS[chosenBoard] }} matches.</p>
      <ul v-else role="list" class="space-y-2">
        <li v-for="deal in matchingDeals" :key="deal.id">
          <button
            type="button"
            :data-testid="`inspection.deal-link.deal.${deal.id}`"
            :disabled="busyDealId !== null || isLinkedTo(deal)"
            class="flex min-h-14 w-full items-center gap-3 rounded-ctl border border-line bg-surface px-4 text-left text-base text-fg transition-colors duration-fast hover:border-fg-muted disabled:opacity-60"
            @click="link(deal)"
          >
            <UiBadge :deal-type="deal.deal_type">{{ deal.deal_type }}</UiBadge>
            <span class="min-w-0 flex-1 truncate">{{ deal.address }}</span>
            <i v-if="busyDealId === deal.id" class="pi pi-spinner pi-spin" aria-hidden="true"></i>
            <i v-else-if="isLinkedTo(deal)" class="pi pi-check text-positive" aria-label="Linked"></i>
          </button>
        </li>
      </ul>
    </div>
  </UiDrawer>
</template>
