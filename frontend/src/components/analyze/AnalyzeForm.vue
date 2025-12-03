<template>
  <form class="space-y-8" @submit.prevent="emitAnalyze">
    <div class="grid gap-6 lg:grid-cols-2">
      <div class="card-surface rounded-2xl p-5 lg:col-span-2">
        <p class="section-heading">Buy & Rehab</p>
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <FieldInput v-model.number="form.arv_in_thousands" label="ARV ($000s)" required @blur="debouncedAnalyze" />
          <FieldInput v-model.number="form.purchasePrice" label="Purchase Price ($000s)" required @blur="debouncedAnalyze" />
          <FieldInput v-model.number="form.rehabCost" label="Rehab Cost ($000s)" @blur="debouncedAnalyze" />
          <FieldInput v-model.number="form.closingCostsBuy" label="Closing Costs (Buy) ($000s)" @blur="debouncedAnalyze" />
          <FieldInput v-model.number="form.down_payment" label="Down Payment %" required @blur="debouncedAnalyze" />
          <FieldInput v-model.number="form.hmlPoints" label="HML Points %" @blur="debouncedAnalyze" />
          <FieldInput v-model.number="form.HMLInterestRate" label="Hard Money Interest %" required @blur="debouncedAnalyze" />
          <FieldInput v-model.number="form.monthsUntilRefi" label="Months until Refi" required @blur="debouncedAnalyze" />
          <ToggleInput v-model="form.use_HM_for_rehab" label="Use HM for Rehab" class="sm:col-span-2 lg:col-span-3" />
        </div>
      </div>

      <div class="card-surface rounded-2xl p-5">
        <p class="section-heading">Refinance</p>
        <div class="grid gap-4 sm:grid-cols-2">
          <div class="space-y-2 sm:col-span-2">
            <div class="flex items-center justify-between">
              <p class="label-text">LTV %</p>
              <span class="text-ocean-900 font-semibold">{{ form.ltv_as_precent.toFixed(1) }}%</span>
            </div>
            <Slider v-model="form.ltv_as_precent" :min="1" :max="100" :step="0.5" @change="debouncedAnalyze" />
          </div>
          <div class="space-y-2 sm:col-span-2">
            <div class="flex items-center justify-between">
              <p class="label-text">Long-term Rate %</p>
              <span class="text-ocean-900 font-semibold">{{ form.interestRate.toFixed(2) }}%</span>
            </div>
            <Slider v-model="form.interestRate" :min="0" :max="20" :step="0.1" @change="debouncedAnalyze" />
          </div>
          <FieldInput v-model.number="form.closingCostsRefi" label="Refi Closing Costs ($000s)" @blur="debouncedAnalyze" />
          <FieldInput v-model.number="form.loanTermYears" label="Loan Term (Years)" @blur="debouncedAnalyze" />
        </div>
      </div>

      <div class="card-surface rounded-2xl p-5 lg:col-span-2">
        <p class="section-heading">Rent & Expenses</p>
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <FieldInput v-model.number="form.rent" label="Rent" prefix="$" required @blur="debouncedAnalyze" />
          <FieldInput v-model.number="form.annual_property_taxes" label="Taxes (Annual)" prefix="$" @blur="debouncedAnalyze" />
          <FieldInput v-model.number="form.annual_insurance" label="Insurance (Annual)" prefix="$" @blur="debouncedAnalyze" />
          <FieldInput v-model.number="form.montly_hoa" label="HOA (Monthly)" prefix="$" @blur="debouncedAnalyze" />
          <FieldInput v-model.number="form.vacancyPercent" label="Vacancy %" @blur="debouncedAnalyze" />
          <FieldInput
            v-model.number="form.property_managment_fee_precentages_from_rent"
            label="Property Mgmt %"
            @blur="debouncedAnalyze"
          />
          <FieldInput v-model.number="form.maintenancePercent" label="Maintenance %" @blur="debouncedAnalyze" />
          <FieldInput v-model.number="form.capexPercent" label="CapEx %" @blur="debouncedAnalyze" />
        </div>
      </div>
    </div>

    <div class="flex flex-wrap items-center justify-between gap-3">
      <p class="text-sm text-slate-400">Required fields are marked with *. Adjust values and analyze instantly.</p>
      <div class="flex gap-2">
        <button type="button" class="rounded-xl bg-ocean-700 px-4 py-2 text-sm font-semibold text-slate-50 shadow-glow" @click="emitSave">
          Save Deal
        </button>
        <button type="submit" class="rounded-xl bg-ocean-900 px-4 py-2 text-sm font-semibold text-slate-50 shadow-glow">
          Analyze
        </button>
      </div>
    </div>
  </form>
</template>

<script setup lang="ts">
import { useDebounceFn } from '@vueuse/core';
import Slider from 'primevue/slider';
import { watch } from 'vue';
import type { AnalyzeDealRequest } from '../../types/deal';
import FieldInput from '../ui/FieldInput.vue';
import ToggleInput from '../ui/ToggleInput.vue';

const props = defineProps<{ form: AnalyzeDealRequest }>();
const emit = defineEmits<{ (e: 'analyze'): void; (e: 'save'): void }>();

const emitAnalyze = () => emit('analyze');
const emitSave = () => emit('save');

const debouncedAnalyze = useDebounceFn(() => emit('analyze'), 300);

watch(
  () => [props.form.ltv_as_precent, props.form.interestRate],
  () => debouncedAnalyze(),
  { deep: true }
);
</script>
