<template>
  <div class="grid gap-6 lg:grid-cols-[2fr_1fr]">
    <section class="space-y-6">
      <h1 class="text-2xl font-semibold text-ocean-900">Analyze Deal</h1>
      <AnalyzeForm :form="form" @analyze="runAnalysis" @save="openSave" />
      <p v-if="error" class="text-sm text-red-400">{{ error }}</p>
    </section>
    <ResultsCard :result="result">
      <template #actions>
        <span v-if="loading" class="text-xs text-slate-400">calculating…</span>
      </template>
    </ResultsCard>
  </div>
  <SaveDealModal v-model:open="saveOpen" :details="saveDetails" @save="handleSave" />
</template>

<script setup lang="ts">
import { reactive, ref, computed } from 'vue';
import AnalyzeForm from '../components/analyze/AnalyzeForm.vue';
import ResultsCard from '../components/analyze/ResultsCard.vue';
import SaveDealModal from '../components/deals/SaveDealModal.vue';
import { analyzeDeal } from '../services/api';
import { useDealsStore } from '../stores/deals';
import type { AdditionalDetails, AnalyzeDealRequest, AnalyzeDealResponse } from '../types/deal';

const store = useDealsStore();
const form = reactive<AnalyzeDealRequest>({
  arv_in_thousands: 300,
  purchasePrice: 200,
  rehabCost: 30,
  down_payment: 20,
  closingCostsBuy: 5,
  use_HM_for_rehab: false,
  hmlPoints: 2,
  monthsUntilRefi: 6,
  HMLInterestRate: 12,
  closingCostsRefi: 5,
  loanTermYears: 30,
  ltv_as_precent: 75,
  interestRate: 7,
  rent: 2400,
  vacancyPercent: 5,
  property_managment_fee_precentages_from_rent: 8,
  maintenancePercent: 5,
  capexPercent: 5,
  annual_property_taxes: 3600,
  annual_insurance: 1200,
  montly_hoa: 0
});

const result = ref<AnalyzeDealResponse | null>(null);
const loading = ref(false);
const error = ref('');
const saveOpen = ref(false);
const saveDetails = reactive<AdditionalDetails>({ section: 1, stage: 1 });

const requiredComplete = computed(() =>
  form.arv_in_thousands > 0 &&
  form.purchasePrice > 0 &&
  form.down_payment >= 0 &&
  form.monthsUntilRefi > 0 &&
  form.HMLInterestRate > 0 &&
  form.ltv_as_precent > 0 &&
  form.interestRate > 0 &&
  form.rent > 0
);

const runAnalysis = async () => {
  if (!requiredComplete.value) {
    error.value = 'Complete all required fields (marked with *) before calculating.';
    return;
  }
  loading.value = true;
  error.value = '';
  try {
    result.value = await analyzeDeal(form);
  } catch (err: any) {
    error.value = err?.response?.data?.detail ?? 'Unable to analyze this deal right now.';
  } finally {
    loading.value = false;
  }
};

const openSave = () => {
  saveOpen.value = true;
};

const handleSave = async (details: AdditionalDetails) => {
  saveOpen.value = false;
  try {
    await store.analyzeAndSave(form, details);
  } catch (err) {
    // handled in store
  }
};
</script>
