<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-semibold text-ocean-900">My Deals</h1>
      <button class="rounded-xl bg-ocean-900 px-4 py-2 text-sm font-semibold text-white shadow-glow" @click="openAdd">
        Add Deal
      </button>
    </div>
    <div class="flex gap-3">
      <button
        v-for="section in sections"
        :key="section.id"
        class="rounded-full px-4 py-2 text-sm"
        :class="section.id === activeSection ? 'bg-ocean-900 text-white' : 'bg-ocean-200/30 text-slate-300'"
        @click="activeSection = section.id"
      >
        {{ section.label }}
      </button>
    </div>

    <div class="grid gap-4 md:grid-cols-5">
      <div v-for="stage in stages" :key="stage.id" class="card-surface rounded-2xl p-3">
        <div class="mb-3 flex items-center justify-between">
          <p class="text-xs uppercase tracking-[0.2em] text-slate-400">{{ stage.label }}</p>
          <span class="text-[10px] rounded-full px-2 py-1 bg-ocean-200/30 text-slate-300">{{ stageLists[stage.id].length }}</span>
        </div>
        <VueDraggable
          v-model="stageLists[stage.id]"
          group="stages"
          item-key="id"
          :animation="180"
          @end="(evt) => onDragEnd(evt, stage.id)"
        >
          <template #item="{ element }">
            <DealCard :deal="element" @select="openDetail(element)" />
          </template>
        </VueDraggable>
      </div>
    </div>
  </div>

  <DealDetailModal v-model:open="detailOpen" :model="activeDeal" @save="saveDetail" />

  <Transition name="fade">
    <div v-if="addOpen" class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 py-8 backdrop-blur">
      <div class="card-surface w-full max-w-6xl rounded-2xl p-6">
        <div class="flex items-center justify-between mb-4">
          <div>
            <p class="text-sm uppercase tracking-[0.2em] text-slate-400">Add Deal</p>
            <p class="text-lg font-semibold text-ocean-900">Analyze, then save to a board</p>
          </div>
          <button class="text-slate-400 hover:text-ocean-900" @click="addOpen = false">✕</button>
        </div>
        <div class="grid gap-6 lg:grid-cols-[2fr_1fr]">
          <AnalyzeForm :form="addForm" @analyze="runAddAnalysis" @save="openAddSave" />
          <ResultsCard :result="addResult">
            <template #actions>
              <span v-if="addLoading" class="text-xs text-slate-400">calculating…</span>
            </template>
          </ResultsCard>
        </div>
      </div>
    </div>
  </Transition>

  <SaveDealModal v-model:open="addSaveOpen" :details="addDetails" @save="saveNewDeal" />
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue';
import { VueDraggable } from 'vue-draggable-plus';
import AnalyzeForm from '../components/analyze/AnalyzeForm.vue';
import ResultsCard from '../components/analyze/ResultsCard.vue';
import DealCard from '../components/deals/DealCard.vue';
import DealDetailModal from '../components/deals/DealDetailModal.vue';
import SaveDealModal from '../components/deals/SaveDealModal.vue';
import { analyzeDeal } from '../services/api';
import { useDealsStore } from '../stores/deals';
import type { AdditionalDetails, AnalyzeDealRequest, AnalyzeDealResponse, Deal, DealSection, DealStage } from '../types/deal';

const store = useDealsStore();
const sections = [
  { id: 1 as DealSection, label: 'Wholesale' },
  { id: 2 as DealSection, label: 'Market' },
  { id: 3 as DealSection, label: 'Our Off Market' }
];
const stages = [
  { id: 1 as DealStage, label: 'New' },
  { id: 2 as DealStage, label: 'Working' },
  { id: 3 as DealStage, label: 'Brought' },
  { id: 4 as DealStage, label: 'Keep in Mind' },
  { id: 5 as DealStage, label: 'Dead' }
];
const activeSection = ref<DealSection>(1);
const detailOpen = ref(false);
const addOpen = ref(false);
const addSaveOpen = ref(false);
const addLoading = ref(false);
const addResult = ref<AnalyzeDealResponse | null>(null);
const activeDeal = ref<Deal | null>(null);
const addDetails = reactive<AdditionalDetails>({ section: 1, stage: 1, address: '' });
const addForm = reactive<AnalyzeDealRequest>({
  arv_in_thousands: 250,
  purchasePrice: 180,
  rehabCost: 25,
  down_payment: 20,
  closingCostsBuy: 5,
  use_HM_for_rehab: false,
  hmlPoints: 2,
  monthsUntilRefi: 6,
  HMLInterestRate: 12,
  closingCostsRefi: 4,
  loanTermYears: 30,
  ltv_as_precent: 72,
  interestRate: 7,
  rent: 2200,
  vacancyPercent: 5,
  property_managment_fee_precentages_from_rent: 8,
  maintenancePercent: 5,
  capexPercent: 5,
  annual_property_taxes: 3000,
  annual_insurance: 1200,
  montly_hoa: 0
});
const stageLists = reactive<Record<DealStage, Deal[]>>({ 1: [], 2: [], 3: [], 4: [], 5: [] });

onMounted(() => {
  store.bootstrap();
});

watch(
  [() => store.deals, () => activeSection.value],
  () => {
    stageLists[1] = store.deals.filter((d) => d.stage === 1 && d.section === activeSection.value);
    stageLists[2] = store.deals.filter((d) => d.stage === 2 && d.section === activeSection.value);
    stageLists[3] = store.deals.filter((d) => d.stage === 3 && d.section === activeSection.value);
    stageLists[4] = store.deals.filter((d) => d.stage === 4 && d.section === activeSection.value);
    stageLists[5] = store.deals.filter((d) => d.stage === 5 && d.section === activeSection.value);
  },
  { deep: true, immediate: true }
);

const onDragEnd = (evt: any, stage: DealStage) => {
  const id = Number(evt?.item?.dataset?.id);
  if (id) {
    store.updateStage(id, stage);
  }
};

const openDetail = (deal: Deal) => {
  activeDeal.value = deal;
  detailOpen.value = true;
};

const saveDetail = (deal: Deal) => {
  store.updateDeal(deal.id, deal);
  detailOpen.value = false;
};

const openAdd = () => {
  addDetails.section = activeSection.value;
  addDetails.stage = 1;
  addDetails.address = '';
  addOpen.value = true;
};

const runAddAnalysis = async () => {
  addLoading.value = true;
  try {
    addResult.value = await analyzeDeal(addForm);
  } catch (err) {
    // swallow
  } finally {
    addLoading.value = false;
  }
};

const openAddSave = () => {
  addSaveOpen.value = true;
};

const saveNewDeal = async (details: AdditionalDetails) => {
  addSaveOpen.value = false;
  addOpen.value = false;
  try {
    await store.analyzeAndSave(addForm, details);
  } catch (err) {
    // handled inside store
  }
};
</script>
