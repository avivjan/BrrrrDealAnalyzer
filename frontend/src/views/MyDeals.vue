<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useDealStore } from "../stores/dealStore";
import { useBoughtDealStore } from "../stores/boughtDealStore";
import { VueDraggable } from "vue-draggable-plus";
import { useDebounceFn, useMediaQuery } from "@vueuse/core";
import {
  formatDealForClipboard,
  ensureBrrrLegacyDefaults,
} from "../utils/dealUtils";
import DealCard from "../components/DealCard.vue";
import DealInputsForm from "../components/DealInputsForm.vue";
import NumberInput from "../components/ui/NumberInput.vue";
import type { ActiveDealRes, AnalyzeDealReq } from "../types";
import api from "../api";

console.group("View: MyDeals");
console.log("Component setup started");

const boughtStore = useBoughtDealStore();
const store = useDealStore();
const route = useRoute();
const router = useRouter();

/** Sortable + Vue can leave list data intact but hide/move DOM on touch; use a plain list there. */
const useSortableBoard = useMediaQuery("(pointer: fine)");

const activeTab = ref(1); // 1=Wholesale, 2=Market, 3=OffMarket
const stages = [
  { id: 1, name: "New - need to analyze", color: "bg-white border-gray-200" },
  { id: 2, name: "Working", color: "bg-white border-gray-200" },
  { id: 3, name: "Brought", color: "bg-white border-gray-200" },
  {
    id: 4,
    name: "Keep in Mind",
    color: "bg-white border-gray-200",
  },
  { id: 5, name: "Dead", color: "bg-white border-gray-200" },
];

// Local state for each column to support drag-and-drop
const columns = ref<Record<number, ActiveDealRes[]>>({
  1: [],
  2: [],
  3: [],
  4: [],
  5: [],
});

// Sync local columns with store data based on active tab
const refreshColumns = () => {
  console.log(
    "View: MyDeals - Refreshing columns for activeTab:",
    activeTab.value
  );
  const tab = Number(activeTab.value);
  const filteredDeals = store.deals.filter(
    (d) => Number(d.section) === tab
  );
  console.log("View: MyDeals - Filtered deals count:", filteredDeals.length);

  // Reset columns
  columns.value = { 1: [], 2: [], 3: [], 4: [], 5: [] };

  filteredDeals.forEach((deal) => {
    const st = Number(deal.stage);
    const stageKey = Number.isFinite(st) ? st : 1;
    if (columns.value[stageKey]) {
      columns.value[stageKey]!.push(deal);
    } else {
      // Fallback for invalid stage
      console.warn(
        "View: MyDeals - Invalid stage for deal, defaulting to 1:",
        deal
      );
      columns.value[1]!.push(deal);
    }
  });
};

watch(
  () => [store.deals, activeTab.value],
  () => {
    console.log(
      "View: MyDeals - deals or activeTab changed, refreshing columns"
    );
    refreshColumns();
  },
  { deep: true }
);

onMounted(async () => {
  console.log("View: MyDeals mounted");
  await store.fetchDeals();
  refreshColumns();

  const openDealId = route.query.openDeal as string | undefined;
  const openDealSection = route.query.section as string | undefined;

  if (openDealId) {
    if (openDealSection) {
      activeTab.value = Number(openDealSection);
    }

    await nextTick();
    refreshColumns();

    const dealToOpen = store.deals.find((d) => d.id === openDealId);
    if (dealToOpen) {
      shouldScrollToResults.value = true;
      openDeal(dealToOpen);
    }

    router.replace({ path: "/my-deals", query: {} });
  }
});

// Handle Drag End
const onDrop = async (event: any, stageId: number) => {
  console.log("View: MyDeals - onDrop event triggered:", { event, stageId });

  if (event.added) {
    const deal = event.added.element;
    console.log(
      "View: MyDeals - Deal dropped into stage (via onDrop):",
      stageId,
      deal
    );

    if (deal.stage !== stageId) {
      // Update local stage immediately for UI consistency
      const oldStage = deal.stage;
      deal.stage = stageId;
      console.log(
        `View: MyDeals - Updating stage locally from ${oldStage} to ${stageId}`
      );

      try {
        await store.updateDealStage(deal.id, stageId);
        console.log("View: MyDeals - Deal stage update sent to store");
      } catch (e) {
        deal.stage = oldStage; // Revert
        console.error(
          "View: MyDeals - Failed to update deal stage in store",
          e
        );
      }
    }
  } else {
    console.log(
      "View: MyDeals - onDrop event ignored (not added):",
      Object.keys(event)
    );
  }
};

const onAdd = async (event: any, stageId: number) => {
  console.log("View: MyDeals - onAdd event triggered:", { event, stageId });
  const list = columns.value[stageId];
  if (list && typeof event.newIndex === "number") {
    const deal = list[event.newIndex];
    if (deal && deal.stage !== stageId) {
      console.log(
        "View: MyDeals - Deal dropped into stage (via onAdd):",
        stageId,
        deal
      );
      const oldStage = deal.stage;
      deal.stage = stageId;
      try {
        await store.updateDealStage(deal.id, stageId);
      } catch (e) {
        deal.stage = oldStage;
        console.error(
          "View: MyDeals - Failed to update deal stage in store (onAdd)",
          e
        );
      }
    }
  }
};

const confirmDelete = async (deal: ActiveDealRes) => {
  console.log("View: MyDeals - confirmDelete requested for deal:", deal.id);
  if (confirm(`Are you sure you want to delete ${deal.address}?`)) {
    try {
      await store.deleteDeal(deal.id, deal.deal_type || 'BRRRR');
      refreshColumns(); // Refresh local columns after store update
      console.log("View: MyDeals - Deal deleted successfully");
    } catch (e) {
      console.error("View: MyDeals - Failed to delete deal", e);
      alert("Failed to delete deal");
    }
  }
};

const duplicateDeal = async (deal: ActiveDealRes) => {
  console.log("View: MyDeals - duplicateDeal requested for deal:", deal.id);
  if (confirm(`Are you sure you want to duplicate this deal?`)) {
    try {
      await store.duplicateDeal(deal.id, deal.deal_type || 'BRRRR');
      refreshColumns(); // Refresh local columns after store update
      console.log("View: MyDeals - Deal duplicated successfully");
    } catch (e) {
      console.error("View: MyDeals - Failed to duplicate deal", e);
      alert("Failed to duplicate deal");
    }
  }
};
const moveToBought = async (deal: ActiveDealRes) => {
  if (confirm("Move this deal to Bought Deals? A copy will be created in the Bought Deals pipeline.")) {
    try {
      await boughtStore.moveToBought(deal.id, deal.deal_type || 'BRRRR');
      alert("Deal moved to Bought Deals successfully!");
    } catch (e) {
      console.error("View: MyDeals - Failed to move deal to bought", e);
      alert("Failed to move deal to Bought Deals");
    }
  }
};

const moveToBoughtFromModal = async () => {
  if (editingDeal.value) {
    if (confirm("Move this deal to Bought Deals? A copy will be created in the Bought Deals pipeline.")) {
      try {
        if (isDirty) await performSave();
        await boughtStore.moveToBought(editingDeal.value.id, editingDeal.value.deal_type || 'BRRRR');
        alert("Deal moved to Bought Deals successfully!");
      } catch (e) {
        console.error("View: MyDeals - Failed to move editing deal to bought", e);
        alert("Failed to move deal to Bought Deals");
      }
    }
  }
};


const duplicateEditingDeal = async () => {
  if (editingDeal.value) {
    if (confirm(`Duplicate this deal?`)) {
      try {
        if (isDirty) await performSave();
        await store.duplicateDeal(editingDeal.value.id, editingDeal.value.deal_type || 'BRRRR');
        showDetailModal.value = false;
      } catch (e) {
        console.error("View: MyDeals - Failed to duplicate editing deal", e);
        alert("Failed to duplicate deal");
      }
    }
  }
};

const deleteEditingDeal = async () => {
  if (editingDeal.value) {
    if (confirm(`Are you sure you want to delete ${editingDeal.value.address}?`)) {
      try {
        await store.deleteDeal(editingDeal.value.id, editingDeal.value.deal_type || 'BRRRR');
        showDetailModal.value = false;
        refreshColumns();
      } catch (e) {
        console.error("View: MyDeals - Failed to delete editing deal", e);
        alert("Failed to delete deal");
      }
    }
  }
};

// Modals
const showDetailModal = ref(false);
const selectedDeal = ref<ActiveDealRes | null>(null);
const editingDeal = ref<ActiveDealRes | null>(null);

const currentAnalysis = ref<ActiveDealRes | null>(null);
const modalScrollContainer = ref<HTMLElement | null>(null);
const analysisResultsEl = ref<HTMLElement | null>(null);
const shouldScrollToResults = ref(false);

const saveStatus = ref<'idle' | 'saving' | 'saved' | 'error'>('idle');
let isDirty = false;
let isInitialLoad = true;
/** Ignore deep-watch churn from inputs mounting (still analyze; no dirty/save). */
let settleUntilMs = 0;
const MODAL_SETTLE_MS = 250;
let savedTimeoutId: ReturnType<typeof setTimeout> | null = null;

const performSave = async () => {
  if (!editingDeal.value || !isDirty) return;
  isDirty = false;
  saveStatus.value = 'saving';
  try {
    const updatedDeal = await store.updateDeal(editingDeal.value);
    if (updatedDeal) {
      currentAnalysis.value = { ...editingDeal.value, ...updatedDeal };
    }
    if (isDirty) {
      debouncedAutoSave();
    } else {
      saveStatus.value = 'saved';
      if (savedTimeoutId) clearTimeout(savedTimeoutId);
      savedTimeoutId = setTimeout(() => { saveStatus.value = 'idle'; }, 2000);
    }
  } catch (e) {
    isDirty = true;
    saveStatus.value = 'error';
    console.error("View: MyDeals - Auto-save failed", e);
  }
};

const debouncedAutoSave = useDebounceFn(performSave, 2000);

const closeModal = async () => {
  if (isDirty && editingDeal.value) {
    await performSave();
  }
  showDetailModal.value = false;
};

const formatCurrency = (value: number | undefined) => {
  if (value === undefined || value === null) return "-";
  if (value === -1) return "∞";
  if (value === -2) return "-∞";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
};

const formatPercent = (value: number | undefined) => {
  if (value === undefined || value === null) return "-";
  if (value === -1) return "∞";
  if (value === -2) return "-∞";
  return `${value.toFixed(2)}%`;
};

const getCashFlowColor = (value: number | undefined) => {
  if (value === undefined || value === null) return "text-gray-900";
  if (value >= 100) return "text-emerald-600";
  if (value >= 1) return "text-gray-600";
  return "text-red-600";
};

const getPerformanceColor = (value: number | undefined) => {
  if (value === undefined || value === null) return "text-gray-900";
  if (value === -1) return "text-emerald-600"; // Infinity
  if (value === -2) return "text-red-600"; // -Infinity
  if (value > 0) return "text-emerald-600";
  if (value < 0) return "text-red-600";
  return "text-gray-600";
};

const getDSCRColor = (value: number | undefined) => {
  if (value === undefined || value === null) return "text-gray-900";
  if (value >= 1.2) return "text-emerald-600";
  if (value >= 1.0) return "text-gray-600";
  return "text-red-600";
};

const openDeal = (deal: ActiveDealRes) => {
  console.log("View: MyDeals - Opening deal detail modal:", deal.id);
  isInitialLoad = true;
  isDirty = false;
  saveStatus.value = 'idle';
  selectedDeal.value = deal;
  const clone = JSON.parse(JSON.stringify(deal)) as ActiveDealRes;
  ensureBrrrLegacyDefaults(clone);
  editingDeal.value = clone;
  currentAnalysis.value = JSON.parse(JSON.stringify(clone));
  settleUntilMs = Date.now() + MODAL_SETTLE_MS;
  showDetailModal.value = true;
};

const analyzeCurrentDeal = useDebounceFn(async () => {
  if (editingDeal.value) {
    console.log(
      "View: MyDeals - Auto-analyzing editing deal:",
      editingDeal.value.id
    );
    try {
      const type = editingDeal.value.deal_type || 'BRRRR';
      // We need to ensure payload matches AnalyzeDealReq.
      // editingDeal (ActiveDealRes) is a superset, but we might need to be explicit or cast.
      // TypeScript error suggests mismatches.
      const payload = JSON.parse(JSON.stringify(editingDeal.value)); // Clone to avoid mutation or proxy issues
      
      const result = await store.analyze(payload as AnalyzeDealReq, type);
      // Merge result into currentAnalysis to display new values
      currentAnalysis.value = { ...editingDeal.value, ...result };
      console.log("View: MyDeals - Analysis result merged into current view");

      if (shouldScrollToResults.value) {
        shouldScrollToResults.value = false;
        await nextTick();
        analysisResultsEl.value?.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    } catch (e) {
      console.error("View: MyDeals - Analysis failed", e);
    }
  }
}, 500);

watch(
  editingDeal,
  () => {
    if (showDetailModal.value) {
      analyzeCurrentDeal();
      if (isInitialLoad) {
        isInitialLoad = false;
        return;
      }
      if (Date.now() < settleUntilMs) {
        return;
      }
      isDirty = true;
      debouncedAutoSave();
    }
  },
  { deep: true }
);

const isHeaderCopied = ref(false);
const isPreparingPdf = ref(false);

// PDF preview modal state. The blob URL is held alive while the modal is open
// and revoked on close to avoid leaking memory.
const pdfPreview = ref<{
  url: string;
  filename: string;
  title: string;
  dealType: "BRRRR" | "FLIP";
} | null>(null);

const copyToClipboard = async (deal: ActiveDealRes) => {
  try {
    const text = formatDealForClipboard(deal);
    await navigator.clipboard.writeText(text);
    console.log("Deal details copied to clipboard");
    isHeaderCopied.value = true;
    setTimeout(() => {
      isHeaderCopied.value = false;
    }, 2000);
  } catch (err) {
    console.error("Failed to copy to clipboard", err);
  }
};

// Generate the report and open it in an in-app preview modal. The user can
// review the PDF inline and only opt into a download from inside the modal.
const viewDealReport = async () => {
  if (!editingDeal.value) return;
  const deal = editingDeal.value;
  const dealType: "BRRRR" | "FLIP" = deal.deal_type === "FLIP" ? "FLIP" : "BRRRR";

  isPreparingPdf.value = true;
  try {
    const address = deal.address || "Property";
    const payload = JSON.parse(JSON.stringify(deal)) as AnalyzeDealReq;
    const blob = await api.downloadDealPdf(payload, dealType, address);
    const url = URL.createObjectURL(blob);
    const filename = `BigWhales_${dealType}_${address.replace(/[^A-Za-z0-9]+/g, "_")}.pdf`;
    closePdfPreview();
    pdfPreview.value = { url, filename, title: address, dealType };
  } catch (err) {
    console.error("Failed to generate deal report", err);
  } finally {
    isPreparingPdf.value = false;
  }
};

const downloadFromPreview = () => {
  if (!pdfPreview.value) return;
  const { url, filename } = pdfPreview.value;
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
};

const closePdfPreview = () => {
  if (pdfPreview.value) {
    URL.revokeObjectURL(pdfPreview.value.url);
    pdfPreview.value = null;
  }
};

onBeforeUnmount(() => {
  closePdfPreview();
});

console.groupEnd();
</script>

<template>
  <div class="h-dvh flex flex-col bg-page text-fg overflow-hidden">
    <!-- Header -->
    <header
      class="flex-none p-4 md:px-8 flex flex-wrap justify-between items-center gap-3 border-b border-line bg-surface/95 md:backdrop-blur z-20 shadow-1"
    >
      <div class="flex items-center gap-3">
        <UiIconButton
          data-testid="mydeals.home"
          @click="$router.push('/')"
          label="Home"
          size="md"
        >
          <i class="pi pi-home text-xl" aria-hidden="true"></i>
        </UiIconButton>
        <UiSectionHeader as="h1" class="hidden md:block">
          My Deals
        </UiSectionHeader>
        <UiButton
          type="button"
          data-testid="mydeals.bought-deals"
          @click="$router.push('/bought-deals')"
          variant="secondary"
          size="sm"
          class="min-h-9 gap-2"
          title="Open bought deals pipeline"
        >
          <i class="pi pi-arrow-circle-right" aria-hidden="true"></i>
          <span class="hidden sm:inline">Bought Deals</span>
        </UiButton>
      </div>

      <!-- Tabs -->
      <UiTabs aria-label="Deal type" class="max-w-full">
        <UiButton
          v-for="tab in [
            {
              id: 1,
              label: 'Wholesale',
              count: store.activeDealsCount.wholesale,
            },
            {
              id: 2,
              label: 'Market',
              count: store.activeDealsCount.market,
            },
            {
              id: 3,
              label: 'Off Market',
              count: store.activeDealsCount.offMarket,
            },
          ]"
          :key="tab.id"
          :data-testid="`mydeals.tab.${tab.id}`"
          @click="activeTab = tab.id"
          variant="tab"
          size="sm"
          :active="activeTab === tab.id"
          class="min-h-9 shrink-0 px-3"
        >
          {{ tab.label }}
          <span
            class="bg-line text-fg-muted px-1.5 py-0.5 rounded-full text-[10px]"
            >{{ tab.count }}</span
          >
        </UiButton>
      </UiTabs>

      <UiButton
        data-testid="mydeals.add-deal"
        @click="$router.push('/analyze')"
        class="ml-auto font-bold shadow-2"
      >
        <i class="pi pi-plus" aria-hidden="true"></i>
        <span class="hidden md:inline">Add Deal</span>
      </UiButton>
    </header>

    <!-- Kanban Board (Refactored to Rows) -->
    <div class="flex-1 min-h-0 overflow-y-auto overflow-x-hidden bg-page pb-safe-b">
      <div
        class="flex flex-col px-4 pb-4 pt-2 md:pt-4 gap-6 w-full max-w-[1920px] mx-auto"
      >
        <UiCard
          v-for="stage in stages"
          :key="stage.id"
          :data-testid="`mydeals.stage.${stage.id}`"
          tone="muted"
          padding="sm"
          class="w-full"
        >
          <!-- Row Header -->
          <template #header>
            <UiSectionHeader as="h3">
              {{ stage.name }}
              <UiBadge
                class="ml-2 align-middle bg-surface px-2.5 font-mono text-sm font-normal text-fg-muted shadow-1 ring-1 ring-inset ring-line"
              >
                {{ columns[stage.id]?.length || 0 }}
              </UiBadge>
            </UiSectionHeader>
          </template>

          <!-- Draggable Area: Sortable breaks Vue DOM on many touch browsers; plain list for coarse pointer -->
          <div>
            <VueDraggable
              v-if="useSortableBoard && columns[stage.id]"
              :data-testid="`mydeals.draggable.${stage.id}`"
              v-model="columns[stage.id]!"
              group="deals"
              @change="(e) => onDrop(e, stage.id)"
              @add="(e) => onAdd(e, stage.id)"
              :animation="150"
              class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-4 min-h-[100px]"
              ghost-class="opacity-50"
            >
              <div
                v-for="deal in columns[stage.id]"
                :key="deal.id"
                :data-testid="`mydeals.card.${deal.id}`"
                @click="openDeal(deal)"
                class="h-full"
              >
                <DealCard
                  :deal="deal"
                  @delete="confirmDelete(deal)"
                  @moveToBought="moveToBought(deal)"
                  @duplicate="duplicateDeal(deal)"
                  class="h-full"
                />
              </div>
            </VueDraggable>
            <div
              v-else-if="columns[stage.id]"
              class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-4 min-h-[100px]"
            >
              <div
                v-for="deal in columns[stage.id]"
                :key="deal.id"
                :data-testid="`mydeals.card.${deal.id}`"
                @click="openDeal(deal)"
                class="h-full"
              >
                <DealCard
                  :deal="deal"
                  @delete="confirmDelete(deal)"
                  @moveToBought="moveToBought(deal)"
                  @duplicate="duplicateDeal(deal)"
                  class="h-full"
                />
              </div>
            </div>
            <UiEmptyState
              v-if="!columns[stage.id]?.length"
              class="mt-3 p-4"
            >
              No deals in this stage
            </UiEmptyState>
          </div>
        </UiCard>
      </div>
    </div>

    <!-- Detail Modal -->
    <div
      v-if="showDetailModal && editingDeal"
      data-testid="mydeals.modal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-fg/40 md:backdrop-blur-sm"
      @click.self="closeModal"
    >
      <UiModalPanel size="xl" labelled-by="mydeals-modal-title">
        <!-- Modal Header -->
        <template #header>
          <div class="flex justify-between items-center gap-3">
          <div class="flex-1 min-w-0 mr-4">
            <div class="flex items-center gap-2 mb-1">
            <label
              id="mydeals-modal-title"
              for="mydeals-modal-address"
              class="text-xs text-fg-muted uppercase font-bold tracking-wider"
                >Address</label>
                 <!-- Type Badge -->
                <UiBadge
                    class="font-bold uppercase tracking-wide"
                    :deal-type="!editingDeal.deal_type || editingDeal.deal_type === 'BRRRR' ? 'BRRRR' : 'FLIP'">
                    {{ (!editingDeal.deal_type || editingDeal.deal_type === 'BRRRR') ? 'BRRRR' : 'FLIP' }}
                </UiBadge>
            </div>
            <input
              id="mydeals-modal-address"
              data-testid="mydeals.modal.address"
              v-model="editingDeal.address"
              class="w-full bg-transparent text-xl md:text-2xl font-bold text-fg border-b border-transparent hover:border-line focus:border-primary outline-none transition-colors"
            />
          </div>
          <div class="flex items-center gap-2">
            <UiButton
              data-testid="mydeals.modal.view-report"
              @click="viewDealReport"
              :disabled="isPreparingPdf"
              variant="secondary"
              size="sm"
              class="min-h-9"
              :title="isPreparingPdf ? 'Building PDF…' : 'Preview Deal Report (Big Whales branded PDF)'"
            >
              <i
                class="pi text-base"
                :class="isPreparingPdf ? 'pi-spin pi-spinner' : 'pi-file-pdf'"
                aria-hidden="true"
              ></i>
              <span class="hidden sm:inline">
                {{ isPreparingPdf ? "Generating…" : "View Report" }}
              </span>
            </UiButton>
            <UiIconButton
              data-testid="mydeals.modal.copy"
              @click="copyToClipboard(editingDeal)"
              label="Copy summary for AI"
              :class="isHeaderCopied ? 'text-positive hover:text-positive' : ''"
              :title="isHeaderCopied ? 'Copied!' : 'Copy Summary for AI'"
            >
              <i
                class="pi text-xl"
                :class="isHeaderCopied ? 'pi-check' : 'pi-file'"
                aria-hidden="true"
              ></i>
            </UiIconButton>
            <UiIconButton
              data-testid="mydeals.modal.close"
              @click="closeModal"
              label="Close"
            >
              <i class="pi pi-times text-xl" aria-hidden="true"></i>
            </UiIconButton>
          </div>
          </div>
        </template>

        <div ref="modalScrollContainer" class="custom-scrollbar overflow-y-auto overscroll-contain">
          <!-- Top Section: Task & Basic Details -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <!-- Central Task Box -->
            <UiCard
              tone="muted"
              class="md:col-span-2"
            >
              <label
                for="mydeals-modal-task"
                class="text-xs text-fg-muted uppercase font-bold tracking-wider mb-2 block"
                >Current Task / Status</label
              >
              <textarea
                id="mydeals-modal-task"
                data-testid="mydeals.modal.task"
                v-model="editingDeal.task"
                class="ui-textarea min-h-[168px] resize-none text-lg"
                placeholder="What needs to be done?"
              ></textarea>
            </UiCard>

            <!-- Basic Details -->
            <div class="space-y-4">
              <div class="grid grid-cols-2 gap-4">
                <NumberInput
                  data-testid="mydeals.modal.sqft"
                  :model-value="editingDeal.sqft ?? null"
                  @update:model-value="(val) => (editingDeal!.sqft = val ?? undefined)"
                  label="SqFt"
                />
                <div class="flex flex-col gap-1">
                  <label for="mydeals-modal-stage" class="text-xs text-fg-muted font-medium">Stage</label>
                  <select
                    id="mydeals-modal-stage"
                    data-testid="mydeals.modal.stage-select"
                    v-model="editingDeal.stage"
                    class="ui-select text-sm"
                  >
                    <option v-for="s in stages" :key="s.id" :value="s.id">
                      {{ s.name }}
                    </option>
                  </select>
                </div>
              </div>
              <div class="grid grid-cols-2 gap-4">
                <NumberInput
                  data-testid="mydeals.modal.bedrooms"
                  :model-value="editingDeal.bedrooms ?? null"
                  @update:model-value="(val) => (editingDeal!.bedrooms = val ?? undefined)"
                  label="Beds"
                />
                <div class="flex flex-col gap-1">
                  <label for="mydeals-modal-section" class="text-xs text-fg-muted font-medium"
                    >Section</label
                  >
                  <select
                    id="mydeals-modal-section"
                    data-testid="mydeals.modal.section"
                    v-model="editingDeal.section"
                    class="ui-select text-sm"
                  >
                    <option :value="1">Wholesale</option>
                    <option :value="2">Market</option>
                    <option :value="3">Off Market</option>
                  </select>
                </div>
              </div>
              <div class="grid grid-cols-2 gap-4">
                <NumberInput
                  data-testid="mydeals.modal.bathrooms"
                  :model-value="editingDeal.bathrooms ?? null"
                  @update:model-value="(val) => (editingDeal!.bathrooms = val ?? undefined)"
                  label="Baths"
                />
                <!-- Placeholder to align grid -->
                <div></div>
              </div>
            </div>
          </div>

          <!-- Quick Links & Additional Info -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div class="space-y-4">
              <div class="flex flex-col gap-1">
                <label for="mydeals-modal-zillow" class="text-xs text-fg-muted font-medium"
                  >Zillow Link</label
                >
                <input
                  id="mydeals-modal-zillow"
                  data-testid="mydeals.modal.zillow-link"
                  v-model="editingDeal.zillow_link"
                  class="ui-input text-sm"
                  placeholder="https://..."
                />
                <a
                  v-if="editingDeal.zillow_link"
                  data-testid="mydeals.modal.zillow-open"
                  :href="editingDeal.zillow_link"
                  target="_blank"
                  class="text-xs text-primary hover:underline inline-flex items-center gap-1 min-h-6"
                  ><i class="pi pi-external-link" aria-hidden="true"></i> Open</a
                >
              </div>
              <div class="flex flex-col gap-1">
                <label for="mydeals-modal-pics" class="text-xs text-fg-muted font-medium"
                  >Photos Link</label
                >
                <input
                  id="mydeals-modal-pics"
                  data-testid="mydeals.modal.pics-link"
                  v-model="editingDeal.pics_link"
                  class="ui-input text-sm"
                  placeholder="Google Drive / Dropbox..."
                />
                <a
                  v-if="editingDeal.pics_link"
                  data-testid="mydeals.modal.pics-open"
                  :href="editingDeal.pics_link"
                  target="_blank"
                  class="text-xs text-primary hover:underline inline-flex items-center gap-1 min-h-6"
                  ><i class="pi pi-external-link" aria-hidden="true"></i> Open</a
                >
              </div>
            </div>
            <div class="space-y-4">
              <div class="flex flex-col gap-1">
                <label for="mydeals-modal-design" class="text-xs text-fg-muted font-medium"
                  >Overall Design</label
                >
                <input
                  id="mydeals-modal-design"
                  data-testid="mydeals.modal.overall-design"
                  v-model="editingDeal.overall_design"
                  class="ui-input text-sm"
                  placeholder="e.g. Modern Farmhouse"
                />
              </div>
              <div class="flex flex-col gap-1">
                <label for="mydeals-modal-crime" class="text-xs text-fg-muted font-medium"
                  >Crime Rate</label
                >
                <input
                  id="mydeals-modal-crime"
                  data-testid="mydeals.modal.crime-rate"
                  v-model="editingDeal.crime_rate"
                  class="ui-input text-sm"
                  placeholder="e.g. Low / B-"
                />
              </div>
            </div>
            <div class="space-y-4">
              <div class="flex flex-col gap-1">
                <label for="mydeals-modal-contact" class="text-xs text-fg-muted font-medium"
                  >Contact Info</label
                >
                <textarea
                  id="mydeals-modal-contact"
                  data-testid="mydeals.modal.contact"
                  v-model="editingDeal.contact"
                  rows="2"
                  class="ui-textarea min-h-0 text-sm"
                  placeholder="Agent / Owner details"
                ></textarea>
              </div>
              <div class="flex flex-col gap-1">
                <label for="mydeals-modal-niche" class="text-xs text-fg-muted font-medium">Niche</label>
                <input
                  id="mydeals-modal-niche"
                  data-testid="mydeals.modal.niche"
                  v-model="editingDeal.niche"
                  class="ui-input text-sm"
                />
              </div>
            </div>
          </div>

          <!-- Analyze Deal Fields (Structured like Analyze Page) -->
          <div class="border-t border-line pt-6 space-y-6">
            
            <DealInputsForm
              :deal="editingDeal"
              :deal-type="editingDeal.deal_type || 'BRRRR'"
              surface="panel"
            />

            <!-- Results Preview -->
            <div ref="analysisResultsEl" v-if="currentAnalysis" data-testid="mydeals.modal.results" class="bg-surface-muted p-4 rounded-card border border-line mb-6">
                <UiSectionHeader as="h4" class="mb-3">Analysis Results</UiSectionHeader>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                    <template v-if="(!editingDeal.deal_type || editingDeal.deal_type === 'BRRRR')">
                        <UiStatTile tone="neutral" class="bg-surface">
                            <template #label>Cash Flow</template>
                            <div data-testid="mydeals.modal.result.cash_flow" class="font-bold" :class="getCashFlowColor((currentAnalysis as any).cash_flow)">{{ formatCurrency((currentAnalysis as any).cash_flow) }}</div>
                        </UiStatTile>
                        <UiStatTile tone="neutral" class="bg-surface">
                            <template #label>Cash Out</template>
                            <div data-testid="mydeals.modal.result.cash_out" class="font-bold" :class="getPerformanceColor((currentAnalysis as any).cash_out)">{{ formatCurrency((currentAnalysis as any).cash_out) }}</div>
                        </UiStatTile>
                        <UiStatTile tone="neutral" class="bg-surface">
                            <template #label>Cash Out Routi</template>
                            <div data-testid="mydeals.modal.result.cash_out_routi" class="font-bold" :class="getPerformanceColor((currentAnalysis as any).cash_out_routi)">{{ formatCurrency((currentAnalysis as any).cash_out_routi) }}</div>
                        </UiStatTile>
                        <UiStatTile tone="neutral" class="bg-surface">
                            <template #label>CoC</template>
                            <div data-testid="mydeals.modal.result.cash_on_cash" class="font-bold" :class="getPerformanceColor((currentAnalysis as any).cash_on_cash)">{{ formatPercent((currentAnalysis as any).cash_on_cash) }}</div>
                        </UiStatTile>
                         <UiStatTile tone="neutral" class="bg-surface">
                             <template #label>DSCR</template>
                             <div data-testid="mydeals.modal.result.dscr" class="font-bold" :class="getDSCRColor((currentAnalysis as any).dscr)">{{ (currentAnalysis as any).dscr?.toFixed(2) || '-' }}</div>
                         </UiStatTile>
                        <UiStatTile tone="neutral" class="bg-surface">
                            <template #label>Equity</template>
                            <div data-testid="mydeals.modal.result.equity" class="font-bold text-positive">{{ formatCurrency((currentAnalysis as any).equity) }}</div>
                        </UiStatTile>
                        <UiStatTile tone="neutral" class="bg-surface">
                            <template #label>ROI</template>
                            <div data-testid="mydeals.modal.result.roi" class="font-bold" :class="getPerformanceColor((currentAnalysis as any).roi)">{{ formatPercent((currentAnalysis as any).roi) }}</div>
                        </UiStatTile>
                        <UiStatTile tone="neutral" class="bg-surface">
                            <template #label>Net Profit</template>
                            <div data-testid="mydeals.modal.result.net_profit" class="font-bold" :class="getPerformanceColor((currentAnalysis as any).net_profit)">{{ formatCurrency((currentAnalysis as any).net_profit) }}</div>
                        </UiStatTile>
                        <UiStatTile tone="neutral" class="bg-surface">
                            <template #label>Total Cash Needed</template>
                            <div data-testid="mydeals.modal.result.total_cash_needed_for_deal" class="font-bold">{{ formatCurrency((currentAnalysis as any).total_cash_needed_for_deal) }}</div>
                        </UiStatTile>
                        <UiStatTile tone="neutral" class="bg-surface">
                            <template #label>Cash Needed (Buffered)</template>
                            <div data-testid="mydeals.modal.result.total_cash_needed_for_deal_with_buffer" class="font-bold">{{ formatCurrency((currentAnalysis as any).total_cash_needed_for_deal_with_buffer) }}</div>
                        </UiStatTile>
                    </template>
                    <template v-else>
                        <UiStatTile tone="neutral" class="bg-surface">
                            <template #label>Net Profit</template>
                            <div data-testid="mydeals.modal.result.net_profit" class="font-bold" :class="getPerformanceColor((currentAnalysis as any).net_profit)">{{ formatCurrency((currentAnalysis as any).net_profit) }}</div>
                        </UiStatTile>
                        <UiStatTile tone="neutral" class="bg-surface">
                            <template #label>ROI</template>
                            <div data-testid="mydeals.modal.result.roi" class="font-bold" :class="getPerformanceColor((currentAnalysis as any).roi)">{{ formatPercent((currentAnalysis as any).roi) }}</div>
                        </UiStatTile>
                        <UiStatTile tone="neutral" class="bg-surface">
                            <template #label>Annualized ROI</template>
                            <div data-testid="mydeals.modal.result.annualized_roi" class="font-bold" :class="getPerformanceColor((currentAnalysis as any).annualized_roi)">{{ formatPercent((currentAnalysis as any).annualized_roi) }}</div>
                        </UiStatTile>
                        <UiStatTile tone="neutral" class="bg-surface">
                            <template #label>Cash Needed</template>
                            <div data-testid="mydeals.modal.result.total_cash_needed" class="font-bold">{{ formatCurrency((currentAnalysis as any).total_cash_needed) }}</div>
                        </UiStatTile>
                        <UiStatTile tone="neutral" class="bg-surface">
                            <template #label>Cash Needed (Buffered)</template>
                            <div data-testid="mydeals.modal.result.total_cash_needed_with_buffer" class="font-bold">{{ formatCurrency((currentAnalysis as any).total_cash_needed_with_buffer) }}</div>
                        </UiStatTile>
                        <UiStatTile tone="neutral" class="bg-surface">
                            <template #label>Holding Costs</template>
                            <div data-testid="mydeals.modal.result.total_holding_costs" class="font-bold">{{ formatCurrency((currentAnalysis as any).total_holding_costs) }}</div>
                        </UiStatTile>
                        <UiStatTile tone="neutral" class="bg-surface">
                            <template #label>HML Interest</template>
                            <div data-testid="mydeals.modal.result.total_hml_interest" class="font-bold">{{ formatCurrency((currentAnalysis as any).total_hml_interest) }}</div>
                        </UiStatTile>
                    </template>
                </div>
            </div>
          </div>

          <!-- Notes -->
          <div class="mt-6">
            <label
              for="mydeals-modal-notes"
              class="text-xs text-fg-muted font-medium uppercase mb-2 block"
              >Notes</label
            >
            <textarea
              id="mydeals-modal-notes"
              data-testid="mydeals.modal.notes"
              v-model="editingDeal.notes"
              rows="4"
              class="ui-textarea p-4 text-sm"
              placeholder="Additional notes..."
            ></textarea>
          </div>

          <!-- Comps Section -->
          <div class="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- Sold Comps -->
            <UiCard tone="muted">
              <UiSectionHeader as="h4" class="mb-4">
                Sold Comps
                <template #actions>
                <UiButton
                  data-testid="mydeals.sold-comp.add"
                  @click="
                    editingDeal.sold_comps
                      ? editingDeal.sold_comps.push({
                          url: '',
                          arv: 0,
                          how_long_ago: '',
                        })
                      : (editingDeal.sold_comps = [
                          { url: '', arv: 0, how_long_ago: '' },
                        ])
                  "
                  variant="secondary"
                  size="sm"
                  class="min-h-8"
                >
                  <i class="pi pi-plus" aria-hidden="true"></i> Add
                </UiButton>
                </template>
              </UiSectionHeader>
              <div
                v-if="
                  editingDeal.sold_comps && editingDeal.sold_comps.length > 0
                "
                class="space-y-3"
              >
                <div
                  v-for="(comp, index) in editingDeal.sold_comps"
                  :key="index"
                  :data-testid="`mydeals.sold-comp.${index}`"
                  class="bg-surface p-2 rounded-ctl relative group border border-line"
                >
                  <UiIconButton
                    :data-testid="`mydeals.sold-comp.${index}.delete`"
                    @click="editingDeal.sold_comps!.splice(index, 1)"
                    label="Remove sold comp"
                    class="absolute -top-2 -right-2 z-10 h-7 w-7 rounded-full bg-negative text-primary-fg text-xs opacity-0 transition-opacity before:-inset-2 hover:bg-negative/90 hover:text-primary-fg group-hover:opacity-100 touch:opacity-100"
                  >
                    ×
                  </UiIconButton>
                  <div class="flex items-center gap-2 mb-1">
                    <input
                      :data-testid="`mydeals.sold-comp.${index}.url`"
                      v-model="comp.url"
                      placeholder="URL"
                      class="flex-1 bg-transparent border-b border-line text-xs focus:border-primary outline-none text-fg"
                    />
                    <a
                      v-if="comp.url"
                      :data-testid="`mydeals.sold-comp.${index}.open`"
                      :href="comp.url"
                      target="_blank"
                      class="text-xs text-primary hover:underline flex-none"
                      ><i class="pi pi-external-link" aria-hidden="true"></i
                    ></a>
                  </div>
                  <div class="flex gap-2">
                    <input
                      :data-testid="`mydeals.sold-comp.${index}.arv`"
                      v-model="comp.arv"
                      type="number"
                      placeholder="ARV"
                      class="w-1/2 bg-transparent border-b border-line text-xs focus:border-primary outline-none text-fg"
                    />
                    <input
                      :data-testid="`mydeals.sold-comp.${index}.age`"
                      v-model="comp.how_long_ago"
                      placeholder="When?"
                      class="w-1/2 bg-transparent border-b border-line text-xs focus:border-primary outline-none text-fg"
                    />
                  </div>
                </div>
              </div>
              <UiEmptyState v-else class="p-4">
                No sold comps added
              </UiEmptyState>
            </UiCard>

            <!-- Rent Comps OR Sale Comps (Flip) -->
            <UiCard tone="muted">
              <UiSectionHeader as="h4" class="mb-4">
                    {{ editingDeal.deal_type === 'FLIP' ? 'For Sale Comps' : 'Rent Comps' }}
                <template #actions>
                <UiButton
                  data-testid="mydeals.comp2.add"
                  @click="
                    editingDeal.deal_type === 'FLIP'
                    ? (
                        (editingDeal as any).sale_comps
                        ? (editingDeal as any).sale_comps.push({ url: '', arv: 0, how_long_ago: '' })
                        : ((editingDeal as any).sale_comps = [{ url: '', arv: 0, how_long_ago: '' }])
                      )
                    : (
                    editingDeal.rent_comps
                        ? editingDeal.rent_comps.push({ url: '', rent: 0, time_on_market: '' })
                        : (editingDeal.rent_comps = [{ url: '', rent: 0, time_on_market: '' }])
                      )
                  "
                  variant="secondary"
                  size="sm"
                  class="min-h-8"
                >
                  <i class="pi pi-plus" aria-hidden="true"></i> Add
                </UiButton>
                </template>
              </UiSectionHeader>

              <!-- Flip Sale Comps -->
              <div v-if="editingDeal.deal_type === 'FLIP'">
                 <div
                    v-if="(editingDeal as any).sale_comps && (editingDeal as any).sale_comps.length > 0"
                    class="space-y-3"
                  >
                    <div
                      v-for="(comp, index) in (editingDeal as any).sale_comps"
                      :key="index"
                      :data-testid="`mydeals.sale-comp.${index}`"
                      class="bg-surface p-2 rounded-ctl relative group border border-line"
                    >
                       <UiIconButton
                        :data-testid="`mydeals.sale-comp.${index}.delete`"
                        @click="(editingDeal as any).sale_comps!.splice(index, 1)"
                        label="Remove sale comp"
                        class="absolute -top-2 -right-2 z-10 h-7 w-7 rounded-full bg-negative text-primary-fg text-xs opacity-0 transition-opacity before:-inset-2 hover:bg-negative/90 hover:text-primary-fg group-hover:opacity-100 touch:opacity-100"
                      >
                        ×
                      </UiIconButton>
                      <div class="flex items-center gap-2 mb-1">
                        <input :data-testid="`mydeals.sale-comp.${index}.url`" v-model="comp.url" placeholder="URL" class="flex-1 bg-transparent border-b border-line text-xs focus:border-primary outline-none text-fg" />
                        <a v-if="comp.url" :data-testid="`mydeals.sale-comp.${index}.open`" :href="comp.url" target="_blank" class="text-xs text-primary hover:underline flex-none"><i class="pi pi-external-link" aria-hidden="true"></i></a>
                      </div>
                      <div class="flex gap-2">
                        <input :data-testid="`mydeals.sale-comp.${index}.arv`" v-model="comp.arv" type="number" placeholder="List Price" class="w-1/2 bg-transparent border-b border-line text-xs focus:border-primary outline-none text-fg" />
                         <input :data-testid="`mydeals.sale-comp.${index}.age`" v-model="comp.how_long_ago" placeholder="Days on Mkt" class="w-1/2 bg-transparent border-b border-line text-xs focus:border-primary outline-none text-fg" />
                      </div>
                    </div>
                 </div>
                 <UiEmptyState v-else class="p-4">No active comps added</UiEmptyState>
              </div>

              <!-- BRRRR Rent Comps -->
              <div v-else>
              <div
                v-if="
                  editingDeal.rent_comps && editingDeal.rent_comps.length > 0
                "
                class="space-y-3"
              >
                <div
                  v-for="(comp, index) in editingDeal.rent_comps"
                  :key="index"
                  :data-testid="`mydeals.rent-comp.${index}`"
                  class="bg-surface p-2 rounded-ctl relative group border border-line"
                >
                  <UiIconButton
                    :data-testid="`mydeals.rent-comp.${index}.delete`"
                    @click="editingDeal.rent_comps!.splice(index, 1)"
                    label="Remove rent comp"
                    class="absolute -top-2 -right-2 z-10 h-7 w-7 rounded-full bg-negative text-primary-fg text-xs opacity-0 transition-opacity before:-inset-2 hover:bg-negative/90 hover:text-primary-fg group-hover:opacity-100 touch:opacity-100"
                  >
                    ×
                  </UiIconButton>
                  <div class="flex items-center gap-2 mb-1">
                    <input
                      :data-testid="`mydeals.rent-comp.${index}.url`"
                      v-model="comp.url"
                      placeholder="URL"
                      class="flex-1 bg-transparent border-b border-line text-xs focus:border-primary outline-none text-fg"
                    />
                    <a
                      v-if="comp.url"
                      :data-testid="`mydeals.rent-comp.${index}.open`"
                      :href="comp.url"
                      target="_blank"
                      class="text-xs text-primary hover:underline flex-none"
                      ><i class="pi pi-external-link" aria-hidden="true"></i
                    ></a>
                  </div>
                  <div class="flex gap-2">
                    <input
                      :data-testid="`mydeals.rent-comp.${index}.rent`"
                      v-model="comp.rent"
                      type="number"
                      placeholder="Rent"
                      class="w-1/2 bg-transparent border-b border-line text-xs focus:border-primary outline-none text-fg"
                    />
                    <input
                      :data-testid="`mydeals.rent-comp.${index}.age`"
                      v-model="comp.time_on_market"
                      placeholder="Time on Market"
                      class="w-1/2 bg-transparent border-b border-line text-xs focus:border-primary outline-none text-fg"
                    />
                  </div>
                </div>
              </div>
              <UiEmptyState v-else class="p-4">
                No rent comps added
                  </UiEmptyState>
              </div>
            </UiCard>
          </div>
        </div>

        <!-- Footer -->
        <template #footer>
        <div
          class="flex flex-wrap gap-x-4 gap-y-2 justify-between items-center"
        >
          <div class="text-xs text-fg-muted">
            Created: {{ new Date(editingDeal.created_at).toLocaleDateString() }}
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <UiSaveStatus data-testid="mydeals.modal.save-status" :data-state="saveStatus" :status="saveStatus" class="mr-1">
              <template v-if="saveStatus === 'saving'">
                <span>Saving...</span>
              </template>
              <template v-else-if="saveStatus === 'saved'">
                <span>Saved</span>
              </template>
              <template v-else-if="saveStatus === 'error'">
                <span>Save failed</span>
              </template>
            </UiSaveStatus>
            <UiButton
              v-if="editingDeal.stage === 3"
              data-testid="mydeals.modal.move-to-bought"
              @click="moveToBoughtFromModal"
              variant="ghost"
              size="sm"
              class="min-h-9 text-positive hover:bg-positive/10"
            >
              <i class="pi pi-arrow-right" aria-hidden="true"></i> Move to Bought
            </UiButton>
            <UiButton
              data-testid="mydeals.modal.delete"
              @click="deleteEditingDeal"
              variant="ghost"
              size="sm"
              class="min-h-9 text-negative hover:bg-negative/10"
            >
              <i class="pi pi-trash" aria-hidden="true"></i> Delete
            </UiButton>
            <UiButton
              data-testid="mydeals.modal.duplicate"
              @click="duplicateEditingDeal"
              variant="ghost"
              size="sm"
              class="min-h-9 text-primary hover:bg-primary/10"
            >
              <i class="pi pi-copy" aria-hidden="true"></i> Duplicate
            </UiButton>
            <UiButton
              data-testid="mydeals.modal.footer-close"
              @click="closeModal"
              variant="ghost"
              size="sm"
              class="min-h-9"
            >
              <i class="pi pi-times" aria-hidden="true"></i> Close
            </UiButton>
          </div>
        </div>
        </template>
      </UiModalPanel>
    </div>

    <!-- PDF Preview Modal -->
    <div
      v-if="pdfPreview"
      data-testid="mydeals.pdf-modal"
      class="fixed inset-0 bg-fg/60 md:backdrop-blur-sm z-[60] flex items-center justify-center p-4"
      @click.self="closePdfPreview"
    >
      <div class="bg-surface w-full max-w-5xl h-[92svh] rounded-panel border border-line shadow-3 flex flex-col overflow-hidden">
        <div class="flex justify-between items-center gap-3 px-5 py-3 border-b border-line shrink-0">
          <div class="flex items-center gap-3 min-w-0">
            <UiBadge
              class="shrink-0 font-bold uppercase tracking-wide"
              :deal-type="pdfPreview.dealType"
            >
              {{ pdfPreview.dealType }}
            </UiBadge>
            <div class="min-w-0">
              <h3 class="text-sm font-bold text-fg truncate">{{ pdfPreview.title }}</h3>
              <p class="text-[11px] text-fg-muted">Deal Report Preview &middot; Big Whales</p>
            </div>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <UiButton
              data-testid="mydeals.pdf-modal.download"
              @click="downloadFromPreview"
              variant="secondary"
              size="sm"
              class="min-h-9 border-positive/30 bg-positive/10 text-positive hover:bg-positive/20"
              title="Download this PDF"
            >
              <i class="pi pi-download text-base" aria-hidden="true"></i>
              <span class="hidden sm:inline">Download</span>
            </UiButton>
            <UiIconButton
              data-testid="mydeals.pdf-modal.close"
              @click="closePdfPreview"
              label="Close preview"
              title="Close preview"
            >
              <i class="pi pi-times text-lg" aria-hidden="true"></i>
            </UiIconButton>
          </div>
        </div>
        <iframe
          data-testid="mydeals.pdf-modal.iframe"
          :src="pdfPreview.url"
          class="flex-1 w-full bg-surface-muted"
          title="Deal Report PDF"
        ></iframe>
      </div>
    </div>
  </div>
</template>
