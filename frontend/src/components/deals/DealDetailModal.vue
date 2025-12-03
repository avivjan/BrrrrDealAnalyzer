<template>
  <Transition name="fade">
    <div v-if="open" class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 py-10 backdrop-blur">
      <div class="card-surface w-full max-w-5xl rounded-2xl p-6">
        <div class="flex items-center justify-between mb-4">
          <div>
            <p class="text-sm text-ocean-900 font-semibold">{{ model?.address }}</p>
            <p class="text-xs text-slate-400">Task: {{ model?.task || '—' }}</p>
          </div>
          <button class="text-slate-400 hover:text-ocean-900" @click="emitClose">✕</button>
        </div>
        <div class="grid gap-6 md:grid-cols-3">
          <div class="md:col-span-2 space-y-4">
            <p class="label-text">Analyze Inputs</p>
            <div class="grid gap-4 md:grid-cols-2">
              <FieldInput v-model.number="draft.arv_in_thousands" label="ARV ($000s)" />
              <FieldInput v-model.number="draft.purchasePrice" label="Purchase Price ($000s)" />
              <FieldInput v-model.number="draft.rehabCost" label="Rehab Cost ($000s)" />
              <FieldInput v-model.number="draft.down_payment" label="Down Payment %" />
              <FieldInput v-model.number="draft.closingCostsBuy" label="Closing Costs Buy ($000s)" />
              <FieldInput v-model.number="draft.hmlPoints" label="HML Points %" />
              <FieldInput v-model.number="draft.HMLInterestRate" label="Hard Money Interest %" />
              <FieldInput v-model.number="draft.monthsUntilRefi" label="Months until Refi" />
              <FieldInput v-model.number="draft.ltv_as_precent" label="LTV %" />
              <FieldInput v-model.number="draft.interestRate" label="Interest Rate %" />
              <FieldInput v-model.number="draft.closingCostsRefi" label="Refi Closing Costs ($000s)" />
              <FieldInput v-model.number="draft.loanTermYears" label="Loan Term Years" />
              <FieldInput v-model.number="draft.rent" label="Rent" />
              <FieldInput v-model.number="draft.vacancyPercent" label="Vacancy %" />
              <FieldInput v-model.number="draft.property_managment_fee_precentages_from_rent" label="Property Mgmt %" />
              <FieldInput v-model.number="draft.maintenancePercent" label="Maintenance %" />
              <FieldInput v-model.number="draft.capexPercent" label="CapEx %" />
              <FieldInput v-model.number="draft.annual_property_taxes" label="Taxes (Annual)" />
              <FieldInput v-model.number="draft.annual_insurance" label="Insurance (Annual)" />
              <FieldInput v-model.number="draft.montly_hoa" label="HOA (Monthly)" />
            </div>
          </div>
          <div class="space-y-4">
            <p class="label-text">Profile</p>
            <label class="space-y-2 block">
              <p class="label-text">Section</p>
              <select v-model.number="draft.section" class="input-base">
                <option :value="1">Wholesale</option>
                <option :value="2">Market</option>
                <option :value="3">Our Off Market</option>
              </select>
            </label>
            <label class="space-y-2 block">
              <p class="label-text">Stage</p>
              <select v-model.number="draft.stage" class="input-base">
                <option :value="1">New</option>
                <option :value="2">Working</option>
                <option :value="3">Brought</option>
                <option :value="4">Keep in Mind</option>
                <option :value="5">Dead</option>
              </select>
            </label>
            <TextInput v-model="draft.address" label="Address" />
            <div class="grid grid-cols-2 gap-3">
              <FieldInput v-model="draft.sqft" label="Sqft" />
              <FieldInput v-model="draft.bedrooms" label="Beds" />
              <FieldInput v-model="draft.bathrooms" label="Baths" />
              <TextInput v-model="draft.contact" label="Contact" />
            </div>
            <TextInput v-model="draft.task" label="Task" />
            <TextInput v-model="draft.zillow_link" label="Zillow" />
            <TextInput v-model="draft.pics_link" label="Pictures" />
            <TextInput v-model="draft.crime_rate" label="Crime" />
            <TextInput v-model="draft.overall_design" label="Design" />
            <label class="space-y-2 block">
              <p class="label-text">Sold Comps (url | arv | age)</p>
              <textarea v-model="soldCompsText" class="input-base min-h-[80px]"></textarea>
            </label>
            <label class="space-y-2 block">
              <p class="label-text">Rent Comps (url | rent | days)</p>
              <textarea v-model="rentCompsText" class="input-base min-h-[80px]"></textarea>
            </label>
            <label class="space-y-2 block">
              <p class="label-text">Notes</p>
              <textarea v-model="draft.notes" class="input-base min-h-[100px]"></textarea>
            </label>
          </div>
        </div>
        <div class="mt-6 flex justify-end gap-2">
          <button class="rounded-xl bg-ocean-200/40 px-4 py-2 text-sm" @click="emitClose">Close</button>
          <button class="rounded-xl bg-ocean-900 px-4 py-2 text-sm font-semibold text-white shadow-glow" @click="emitSave">
            Save Changes
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue';
import type { Deal } from '../../types/deal';
import FieldInput from '../ui/FieldInput.vue';
import TextInput from '../ui/TextInput.vue';

const props = defineProps<{ open: boolean; model: Deal | null }>();
const emit = defineEmits<{ (e: 'update:open', value: boolean): void; (e: 'save', value: Deal): void }>();

const draft = reactive<Deal | any>({ ...props.model });
const soldCompsText = ref('');
const rentCompsText = ref('');

watch(
  () => props.model,
  (value) => {
    Object.assign(draft, value || {});
    soldCompsText.value = (value?.sold_comps || [])
      .map((c) => `${c.url} | ${c.arv} | ${c.how_long_ago}`)
      .join('\n');
    rentCompsText.value = (value?.rent_comps || [])
      .map((c) => `${c.url} | ${c.rent} | ${c.time_on_market}`)
      .join('\n');
  },
  { deep: true }
);

const emitClose = () => emit('update:open', false);
const emitSave = () => {
  if (props.model) {
    const sold = soldCompsText.value
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [url, arv, age] = line.split('|').map((p) => p.trim());
        return { url, arv: Number(arv), how_long_ago: age };
      });
    const rent = rentCompsText.value
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [url, rent, days] = line.split('|').map((p) => p.trim());
        return { url, rent: Number(rent), time_on_market: days };
      });
    emit('save', { ...props.model, ...draft, sold_comps: sold, rent_comps: rent });
  }
};
</script>
