<script setup lang="ts">
import { ref, watch, onMounted } from "vue";
import { useDealStore } from "../stores/dealStore";
import { VueDraggable } from "vue-draggable-plus";
import { useDebounceFn } from "@vueuse/core";
import DealCard from "../components/DealCard.vue";
import MoneyInput from "../components/ui/MoneyInput.vue";
import NumberInput from "../components/ui/NumberInput.vue";
import SliderField from "../components/ui/SliderField.vue";
import ToggleSwitch from "primevue/toggleswitch";
import type { ActiveDealRes } from "../types";

const store = useDealStore();

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
  const filteredDeals = store.deals.filter(
    (d) => d.section === activeTab.value
  );

  // Reset columns
  columns.value = { 1: [], 2: [], 3: [], 4: [], 5: [] };

  filteredDeals.forEach((deal) => {
    if (columns.value[deal.stage]) {
      columns.value[deal.stage]!.push(deal);
    } else {
      // Fallback for invalid stage
      columns.value[1]!.push(deal);
    }
  });
};

watch(
  () => [store.deals, activeTab.value],
  () => {
    refreshColumns();
  },
  { deep: true }
);

onMounted(async () => {
  await store.fetchDeals();
  refreshColumns();
});

// Handle Drag End
const onDrop = (event: any, stageId: number) => {
  if (event.added) {
    const deal = event.added.element;
    store.updateDealStage(deal.id, stageId);
  }
};

const confirmDelete = async (deal: ActiveDealRes) => {
  if (confirm(`Are you sure you want to delete ${deal.address}?`)) {
    try {
      await store.deleteDeal(deal.id);
      refreshColumns(); // Refresh local columns after store update
    } catch (e) {
      alert("Failed to delete deal");
    }
  }
};

const duplicateDeal = async (dealId: number) => {
  if (confirm(`Are you sure you want to duplicate this deal?`)) {
    try {
      await store.duplicateDeal(dealId);
      refreshColumns(); // Refresh local columns after store update
    } catch (e) {
      alert("Failed to duplicate deal");
    }
  }
};

const duplicateEditingDeal = async () => {
  if (editingDeal.value) {
    if (confirm(`Duplicate this deal?`)) {
      try {
        await store.duplicateDeal(editingDeal.value.id);
        showDetailModal.value = false; // Close modal after duplicate
      } catch (e) {
        alert("Failed to duplicate deal");
      }
    }
  }
};

// Modals
const showDetailModal = ref(false);
const selectedDeal = ref<ActiveDealRes | null>(null);
const editingDeal = ref<ActiveDealRes | null>(null);
const currentAnalysis = ref<ActiveDealRes | null>(null);

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
  selectedDeal.value = deal;
  editingDeal.value = JSON.parse(JSON.stringify(deal));
  currentAnalysis.value = JSON.parse(JSON.stringify(deal)); // Initialize with stored results
  showDetailModal.value = true;
};

const analyzeCurrentDeal = useDebounceFn(async () => {
  if (editingDeal.value) {
    try {
      const result = await store.analyze(editingDeal.value);
      // Merge result into currentAnalysis to display new values
      currentAnalysis.value = { ...editingDeal.value, ...result };
    } catch (e) {
      console.error("Analysis failed", e);
    }
  }
}, 500);

watch(
  editingDeal,
  () => {
    if (showDetailModal.value) {
      analyzeCurrentDeal();
    }
  },
  { deep: true }
);

const saveChanges = async () => {
  if (editingDeal.value) {
    try {
      await store.updateDeal(editingDeal.value);
      showDetailModal.value = false;
    } catch (e) {
      alert("Failed to save changes");
    }
  }
};
</script>

<template>
  <div class="h-screen flex flex-col bg-gray-50 text-gray-900 overflow-hidden">
    <!-- Header -->
    <header
      class="flex-none p-4 md:px-8 flex justify-between items-center border-b border-gray-200 bg-white/95 backdrop-blur z-20 shadow-sm"
    >
      <div class="flex items-center gap-4">
        <button
          @click="$router.push('/')"
          class="text-gray-500 hover:text-blue-600 transition-colors"
        >
          <i class="pi pi-home text-xl"></i>
        </button>
        <h1 class="text-2xl font-bold text-gray-900 hidden md:block">
          My Deals
        </h1>
      </div>

      <!-- Tabs -->
      <div class="flex bg-gray-100 rounded-lg p-1 border border-gray-200">
        <button
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
          @click="activeTab = tab.id"
          class="px-3 py-1.5 text-sm font-medium rounded-md transition-all flex items-center gap-2"
          :class="
            activeTab === tab.id
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          "
        >
          {{ tab.label }}
          <span
            class="bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded-full text-[10px]"
            >{{ tab.count }}</span
          >
        </button>
      </div>

      <button
        @click="$router.push('/analyze')"
        class="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-bold shadow-lg flex items-center gap-2 transition-all"
      >
        <i class="pi pi-plus"></i>
        <span class="hidden md:inline">Add Deal</span>
      </button>
    </header>

    <!-- Kanban Board -->
    <div class="flex-1 overflow-x-auto overflow-y-hidden bg-gray-50">
      <div class="h-full flex px-4 pb-4 pt-2 md:pt-4 gap-4 min-w-max">
        <div
          v-for="stage in stages"
          :key="stage.id"
          class="flex flex-col w-[85vw] md:w-80 h-full rounded-xl border shadow-sm transition-colors"
          :class="stage.color"
        >
          <!-- Column Header -->
          <div
            class="flex-none p-3 flex justify-between items-center border-b border-gray-100"
          >
            <h3 class="font-bold text-gray-800">{{ stage.name }}</h3>
            <span
              class="bg-gray-100 px-2 py-0.5 rounded-full text-xs font-mono text-gray-500"
            >
              {{ columns[stage.id]?.length || 0 }}
            </span>
          </div>

          <!-- Draggable Area -->
          <div class="flex-1 overflow-y-auto p-3 scrollbar-hide bg-gray-50/50">
            <VueDraggable
              v-if="columns[stage.id]"
              v-model="columns[stage.id]!"
              group="deals"
              @change="(e) => onDrop(e, stage.id)"
              :animation="150"
              class="flex flex-col gap-3 min-h-[100px]"
              ghost-class="opacity-50"
            >
              <div
                v-for="deal in columns[stage.id]"
                :key="deal.id"
                @click="openDeal(deal)"
              >
                <DealCard
                  :deal="deal"
                  @delete="confirmDelete(deal)"
                  @duplicate="duplicateDeal(deal.id)"
                />
              </div>
            </VueDraggable>
          </div>
        </div>
      </div>
    </div>

    <!-- Detail Modal -->
    <div
      v-if="showDetailModal && editingDeal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
    >
      <div
        class="bg-white w-full max-w-6xl max-h-[95vh] rounded-2xl border border-gray-200 shadow-2xl flex flex-col"
      >
        <!-- Modal Header -->
        <div
          class="flex justify-between items-center p-6 border-b border-gray-100 shrink-0"
        >
          <div class="flex-1 mr-4">
            <label
              class="text-xs text-gray-500 uppercase font-bold tracking-wider"
              >Address</label
            >
            <input
              v-model="editingDeal.address"
              class="w-full bg-transparent text-2xl font-bold text-gray-900 border-b border-transparent hover:border-gray-200 focus:border-blue-500 outline-none transition-colors"
            />
          </div>
          <button
            @click="showDetailModal = false"
            class="text-gray-400 hover:text-gray-600"
          >
            <i class="pi pi-times text-xl"></i>
          </button>
        </div>

        <div class="p-6 overflow-y-auto custom-scrollbar">
          <!-- Top Section: Task & Basic Details -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <!-- Central Task Box -->
            <div
              class="md:col-span-2 bg-gray-50 p-4 rounded-xl border border-gray-200 flex flex-col justify-start min-h-[200px]"
            >
              <label
                class="text-xs text-gray-500 uppercase font-bold tracking-wider mb-2"
                >Current Task / Status</label
              >
              <textarea
                v-model="editingDeal.task"
                class="w-full h-full bg-transparent text-lg text-gray-800 resize-none outline-none placeholder-gray-400"
                placeholder="What needs to be done?"
              ></textarea>
            </div>

            <!-- Basic Details -->
            <div class="space-y-4">
              <div class="grid grid-cols-2 gap-4">
                <NumberInput
                  :model-value="editingDeal.sqft ?? null"
                  @update:model-value="(val) => (editingDeal!.sqft = val ?? undefined)"
                  label="SqFt"
                />
                <div class="flex flex-col gap-1">
                  <label class="text-xs text-gray-600 font-medium">Stage</label>
                  <select
                    v-model="editingDeal.stage"
                    class="bg-gray-50 border border-gray-200 rounded-lg px-2 py-2 text-gray-900 text-sm outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    <option v-for="s in stages" :key="s.id" :value="s.id">
                      {{ s.name }}
                    </option>
                  </select>
                </div>
              </div>
              <div class="grid grid-cols-2 gap-4">
                <NumberInput
                  :model-value="editingDeal.bedrooms ?? null"
                  @update:model-value="(val) => (editingDeal!.bedrooms = val ?? undefined)"
                  label="Beds"
                />
                <div class="flex flex-col gap-1">
                  <label class="text-xs text-gray-600 font-medium"
                    >Section</label
                  >
                  <select
                    v-model="editingDeal.section"
                    class="bg-gray-50 border border-gray-200 rounded-lg px-2 py-2 text-gray-900 text-sm outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    <option :value="1">Wholesale</option>
                    <option :value="2">Market</option>
                    <option :value="3">Off Market</option>
                  </select>
                </div>
              </div>
              <div class="grid grid-cols-2 gap-4">
                <NumberInput
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
                <label class="text-xs text-gray-600 font-medium"
                  >Zillow Link</label
                >
                <input
                  v-model="editingDeal.zillow_link"
                  class="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-gray-900 text-sm outline-none focus:border-blue-500"
                  placeholder="https://..."
                />
                <a
                  v-if="editingDeal.zillow_link"
                  :href="editingDeal.zillow_link"
                  target="_blank"
                  class="text-xs text-blue-500 hover:text-blue-700 flex items-center gap-1"
                  ><i class="pi pi-external-link"></i> Open</a
                >
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-xs text-gray-600 font-medium"
                  >Photos Link</label
                >
                <input
                  v-model="editingDeal.pics_link"
                  class="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-gray-900 text-sm outline-none focus:border-blue-500"
                  placeholder="Google Drive / Dropbox..."
                />
                <a
                  v-if="editingDeal.pics_link"
                  :href="editingDeal.pics_link"
                  target="_blank"
                  class="text-xs text-blue-500 hover:text-blue-700 flex items-center gap-1"
                  ><i class="pi pi-external-link"></i> Open</a
                >
              </div>
            </div>
            <div class="space-y-4">
              <div class="flex flex-col gap-1">
                <label class="text-xs text-gray-600 font-medium"
                  >Overall Design</label
                >
                <input
                  v-model="editingDeal.overall_design"
                  class="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-gray-900 text-sm outline-none focus:border-blue-500"
                  placeholder="e.g. Modern Farmhouse"
                />
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-xs text-gray-600 font-medium"
                  >Crime Rate</label
                >
                <input
                  v-model="editingDeal.crime_rate"
                  class="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-gray-900 text-sm outline-none focus:border-blue-500"
                  placeholder="e.g. Low / B-"
                />
              </div>
            </div>
            <div class="space-y-4">
              <div class="flex flex-col gap-1">
                <label class="text-xs text-gray-600 font-medium"
                  >Contact Info</label
                >
                <textarea
                  v-model="editingDeal.contact"
                  rows="2"
                  class="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-gray-900 text-sm outline-none focus:border-blue-500"
                  placeholder="Agent / Owner details"
                ></textarea>
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-xs text-gray-600 font-medium">Niche</label>
                <input
                  v-model="editingDeal.niche"
                  class="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-gray-900 text-sm outline-none focus:border-blue-500"
                />
              </div>
            </div>
          </div>

          <!-- Analyze Deal Fields -->
          <div class="border-t border-gray-200 pt-6">
            <div class="flex justify-between items-center mb-6">
              <h3
                class="text-xl font-bold text-gray-800 flex items-center gap-2"
              >
                <i class="pi pi-calculator text-blue-500"></i> Deal Analysis
              </h3>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
              <!-- Group 1: Buy & Rehab -->
              <div class="bg-gray-50 p-4 rounded-xl border border-gray-200">
                <h4 class="font-semibold text-gray-700 mb-4">Buy & Rehab</h4>
                <div class="space-y-3">
                  <MoneyInput
                    v-model="editingDeal.purchasePrice"
                    label="Purchase Price"
                    :inThousands="true"
                  />
                  <MoneyInput
                    v-model="editingDeal.rehabCost"
                    label="Rehab Cost"
                    :inThousands="true"
                  />
                  <MoneyInput
                    v-model="editingDeal.closingCostsBuy"
                    label="Closing Costs (Buy)"
                    :inThousands="true"
                  />

                  <div class="pt-2 border-t border-gray-200">
                    <p class="text-xs text-gray-500 mb-2">Hard Money</p>
                    <div class="grid grid-cols-2 gap-2">
                      <NumberInput
                        v-model="editingDeal.down_payment"
                        label="Down Pmt %"
                        :min="0"
                        :max="100"
                      />
                      <NumberInput
                        v-model="editingDeal.hmlPoints"
                        label="Points"
                        :min="0"
                        :max="100"
                      />
                      <NumberInput
                        v-model="editingDeal.HMLInterestRate"
                        label="Rate %"
                        :min="0"
                        :max="100"
                      />
                      <div class="flex flex-col justify-end">
                        <div
                          class="flex items-center justify-between bg-white p-2 rounded border border-gray-200"
                        >
                          <span class="text-[10px] text-gray-600"
                            >HM for Rehab</span
                          >
                          <ToggleSwitch
                            v-model="editingDeal.use_HM_for_rehab"
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Group 2: Refinance -->
              <div class="bg-gray-50 p-4 rounded-xl border border-gray-200">
                <h4 class="font-semibold text-gray-700 mb-4">
                  Refinance (BRRRR)
                </h4>
                <div class="space-y-3">
                  <MoneyInput
                    v-model="editingDeal.arv_in_thousands"
                    label="ARV"
                    :inThousands="true"
                  />
                  <SliderField
                    v-model="editingDeal.ltv_as_precent"
                    label="LTV %"
                    :min="1"
                    :max="100"
                  />
                  <div class="grid grid-cols-2 gap-2">
                    <NumberInput
                      v-model="editingDeal.monthsUntilRefi"
                      label="Months to Refi"
                    />
                    <MoneyInput
                      v-model="editingDeal.closingCostsRefi"
                      label="Refi Costs"
                      :inThousands="true"
                    />
                  </div>
                  <SliderField
                    v-model="editingDeal.interestRate"
                    label="Interest Rate %"
                    :min="0"
                    :max="15"
                    :step="0.125"
                  />
                  <NumberInput
                    v-model="editingDeal.loanTermYears"
                    label="Loan Term (Yrs)"
                  />
                </div>
              </div>

              <!-- Group 3: Rent & Expenses -->
              <div class="bg-gray-50 p-4 rounded-xl border border-gray-200">
                <h4 class="font-semibold text-gray-700 mb-4">
                  Rent & Expenses
                </h4>
                <div class="space-y-3">
                  <MoneyInput v-model="editingDeal.rent" label="Monthly Rent" />
                  <div class="grid grid-cols-2 gap-2">
                    <MoneyInput
                      v-model="editingDeal.annual_property_taxes"
                      label="Annual Taxes"
                    />
                    <MoneyInput
                      v-model="editingDeal.annual_insurance"
                      label="Annual Ins."
                    />
                  </div>
                  <MoneyInput
                    v-model="editingDeal.montly_hoa"
                    label="Monthly HOA"
                  />

                  <div class="grid grid-cols-2 gap-2">
                    <NumberInput
                      v-model="editingDeal.vacancyPercent"
                      label="Vacancy %"
                    />
                    <NumberInput
                      v-model="editingDeal.maintenancePercent"
                      label="Maint. %"
                    />
                    <NumberInput
                      v-model="editingDeal.capexPercent"
                      label="CapEx %"
                    />
                    <NumberInput
                      v-model="
                        editingDeal.property_managment_fee_precentages_from_rent
                      "
                      label="Mgmt %"
                    />
                  </div>
                </div>
              </div>
            </div>

            <!-- Analysis Results -->
            <div
              v-if="currentAnalysis"
              class="bg-white p-6 rounded-2xl border border-gray-200 shadow-xl relative overflow-hidden"
            >
              <div
                class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-500 to-indigo-500"
              ></div>
              <h4
                class="font-semibold text-gray-800 mb-6 flex items-center gap-2"
              >
                <i class="pi pi-chart-bar text-blue-500"></i> Analysis Results
              </h4>
              <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
                <!-- Primary Metrics -->
                <div class="space-y-1">
                  <div class="text-xs text-gray-500 uppercase">Cash Flow</div>
                  <div
                    class="text-2xl font-bold"
                    :class="getCashFlowColor(currentAnalysis.cash_flow)"
                  >
                    {{ formatCurrency(currentAnalysis.cash_flow) }}
                  </div>
                </div>
                <div class="space-y-1">
                  <div class="text-xs text-gray-500 uppercase">Cash Out</div>
                  <div
                    class="text-2xl font-bold"
                    :class="getPerformanceColor(currentAnalysis.cash_out)"
                  >
                    {{ formatCurrency(currentAnalysis.cash_out) }}
                  </div>
                </div>
                <div class="space-y-1">
                  <div class="text-xs text-gray-500 uppercase">Cash Needed</div>
                  <div class="text-2xl font-bold text-blue-600">
                    {{
                      formatCurrency(currentAnalysis.total_cash_needed_for_deal)
                    }}
                  </div>
                </div>
                <div class="space-y-1">
                  <div class="text-xs text-gray-500 uppercase">DSCR</div>
                  <div
                    class="text-2xl font-bold"
                    :class="getDSCRColor(currentAnalysis.dscr)"
                  >
                    {{ currentAnalysis.dscr?.toFixed(2) ?? "-" }}
                  </div>
                </div>

                <!-- Secondary Metrics -->
                <div class="space-y-1">
                  <div class="text-xs text-gray-500 uppercase">CoC Return</div>
                  <div
                    class="text-lg font-medium"
                    :class="getPerformanceColor(currentAnalysis.cash_on_cash)"
                  >
                    {{ formatPercent(currentAnalysis.cash_on_cash) }}
                  </div>
                </div>
                <div class="space-y-1">
                  <div class="text-xs text-gray-500 uppercase">ROI</div>
                  <div
                    class="text-lg font-medium"
                    :class="getPerformanceColor(currentAnalysis.roi)"
                  >
                    {{ formatPercent(currentAnalysis.roi) }}
                  </div>
                </div>
                <div class="space-y-1">
                  <div class="text-xs text-gray-500 uppercase">Equity</div>
                  <div
                    class="text-lg font-medium"
                    :class="getPerformanceColor(currentAnalysis.equity)"
                  >
                    {{ formatCurrency(currentAnalysis.equity) }}
                  </div>
                </div>
                <div class="space-y-1">
                  <div class="text-xs text-gray-500 uppercase">Net Profit</div>
                  <div
                    class="text-lg font-medium"
                    :class="getPerformanceColor(currentAnalysis.net_profit)"
                  >
                    {{ formatCurrency(currentAnalysis.net_profit) }}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Notes -->
          <div class="mt-6">
            <label
              class="text-xs text-gray-600 font-medium uppercase mb-2 block"
              >Notes</label
            >
            <textarea
              v-model="editingDeal.notes"
              rows="4"
              class="w-full bg-gray-50 border border-gray-200 rounded-lg p-4 text-gray-900 text-sm outline-none focus:border-blue-500"
              placeholder="Additional notes..."
            ></textarea>
          </div>

          <!-- Comps Section -->
          <div class="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- Sold Comps -->
            <div class="bg-gray-50 p-4 rounded-xl border border-gray-200">
              <div class="flex justify-between items-center mb-4">
                <h4 class="font-semibold text-gray-700">Sold Comps</h4>
                <button
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
                  class="text-xs bg-blue-600 px-2 py-1 rounded text-white hover:bg-blue-500"
                >
                  <i class="pi pi-plus"></i> Add
                </button>
              </div>
              <div
                v-if="
                  editingDeal.sold_comps && editingDeal.sold_comps.length > 0
                "
                class="space-y-3"
              >
                <div
                  v-for="(comp, index) in editingDeal.sold_comps"
                  :key="index"
                  class="bg-white p-2 rounded relative group border border-gray-100"
                >
                  <button
                    @click="editingDeal.sold_comps!.splice(index, 1)"
                    class="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity z-10"
                  >
                    ×
                  </button>
                  <div class="flex items-center gap-2 mb-1">
                    <input
                      v-model="comp.url"
                      placeholder="URL"
                      class="flex-1 bg-transparent border-b border-gray-100 text-xs focus:border-blue-500 outline-none text-gray-700"
                    />
                    <a
                      v-if="comp.url"
                      :href="comp.url"
                      target="_blank"
                      class="text-xs text-blue-500 hover:text-blue-700 flex-none"
                      ><i class="pi pi-external-link"></i
                    ></a>
                  </div>
                  <div class="flex gap-2">
                    <input
                      v-model="comp.arv"
                      type="number"
                      placeholder="ARV"
                      class="w-1/2 bg-transparent border-b border-gray-100 text-xs focus:border-blue-500 outline-none text-gray-700"
                    />
                    <input
                      v-model="comp.how_long_ago"
                      placeholder="When?"
                      class="w-1/2 bg-transparent border-b border-gray-100 text-xs focus:border-blue-500 outline-none text-gray-700"
                    />
                  </div>
                </div>
              </div>
              <div v-else class="text-xs text-gray-400 italic text-center py-4">
                No sold comps added
              </div>
            </div>

            <!-- Rent Comps -->
            <div class="bg-gray-50 p-4 rounded-xl border border-gray-200">
              <div class="flex justify-between items-center mb-4">
                <h4 class="font-semibold text-gray-700">Rent Comps</h4>
                <button
                  @click="
                    editingDeal.rent_comps
                      ? editingDeal.rent_comps.push({
                          url: '',
                          rent: 0,
                          time_on_market: '',
                        })
                      : (editingDeal.rent_comps = [
                          { url: '', rent: 0, time_on_market: '' },
                        ])
                  "
                  class="text-xs bg-blue-600 px-2 py-1 rounded text-white hover:bg-blue-500"
                >
                  <i class="pi pi-plus"></i> Add
                </button>
              </div>
              <div
                v-if="
                  editingDeal.rent_comps && editingDeal.rent_comps.length > 0
                "
                class="space-y-3"
              >
                <div
                  v-for="(comp, index) in editingDeal.rent_comps"
                  :key="index"
                  class="bg-white p-2 rounded relative group border border-gray-100"
                >
                  <button
                    @click="editingDeal.rent_comps!.splice(index, 1)"
                    class="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity z-10"
                  >
                    ×
                  </button>
                  <div class="flex items-center gap-2 mb-1">
                    <input
                      v-model="comp.url"
                      placeholder="URL"
                      class="flex-1 bg-transparent border-b border-gray-100 text-xs focus:border-blue-500 outline-none text-gray-700"
                    />
                    <a
                      v-if="comp.url"
                      :href="comp.url"
                      target="_blank"
                      class="text-xs text-blue-500 hover:text-blue-700 flex-none"
                      ><i class="pi pi-external-link"></i
                    ></a>
                  </div>
                  <div class="flex gap-2">
                    <input
                      v-model="comp.rent"
                      type="number"
                      placeholder="Rent"
                      class="w-1/2 bg-transparent border-b border-gray-100 text-xs focus:border-blue-500 outline-none text-gray-700"
                    />
                    <input
                      v-model="comp.time_on_market"
                      placeholder="Time on Market"
                      class="w-1/2 bg-transparent border-b border-gray-100 text-xs focus:border-blue-500 outline-none text-gray-700"
                    />
                  </div>
                </div>
              </div>
              <div v-else class="text-xs text-gray-400 italic text-center py-4">
                No rent comps added
              </div>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div
          class="p-6 border-t border-gray-200 flex justify-between items-center bg-gray-50 rounded-b-2xl"
        >
          <div class="text-xs text-gray-500">
            Created: {{ new Date(editingDeal.created_at).toLocaleDateString() }}
          </div>
          <div class="flex gap-4">
            <button
              @click="duplicateEditingDeal"
              class="text-blue-600 hover:text-blue-800 px-4 py-2 flex items-center gap-2"
            >
              <i class="pi pi-copy"></i> Duplicate
            </button>
            <button
              @click="showDetailModal = false"
              class="text-gray-500 hover:text-gray-700 px-4 py-2"
            >
              Cancel
            </button>
            <button
              @click="saveChanges"
              class="bg-blue-600 hover:bg-blue-500 text-white font-bold px-8 py-2 rounded-xl shadow-lg transition-all transform hover:scale-[1.02] active:scale-95 flex items-center gap-2"
            >
              <i class="pi pi-save"></i> Save Changes
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Custom Scrollbar for columns */
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
