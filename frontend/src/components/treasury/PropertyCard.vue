<script setup lang="ts">
import { computed } from 'vue'
import type { LLCConfiguration, PropertyStatus } from '../../types/treasury'
import BucketRing from './BucketRing.vue'
import InlineEditValue from './InlineEditValue.vue'
import InfoTip from './InfoTip.vue'
import KebabMenu from './KebabMenu.vue'

const props = defineProps<{
  property: PropertyStatus
  llcs: LLCConfiguration[]
  disabled?: boolean
}>()

const emit = defineEmits<{
  patch: [field: string, value: number | boolean | string]
  delete: []
  'open-cash-flow': []
  'open-settings': []
  'move-llc': [llcId: string]
}>()

const hasDebt = computed(() => props.property.reserve_debt > 0)

const TO_SETTLE_TIP =
  'Amount still owed to this bucket this cycle — rent allocations not yet moved or reconciled.'
const DEBT_TO_SAVINGS_TIP =
  'Reserve shortfall carried forward from prior cycles — dollars still owed back to the savings bucket.'

function patch(field: string, value: number | boolean | string) {
  emit('patch', field, value)
}
</script>

<template>
  <div class="property-card">
    <div class="mb-3 flex items-start justify-between gap-2">
      <div class="min-w-0">
        <InlineEditValue
          :model-value="property.property_name"
          :disabled="disabled"
          class="text-[0.95rem] font-bold text-white"
          @commit="(v) => patch('property_name', v)"
        />
        <code class="mt-0.5 block text-[0.6rem] text-white/25">{{ property.property_id.slice(0, 8) }}…</code>
      </div>
      <KebabMenu>
        <template #default="{ close }">
          <button
            type="button"
            class="kebab-item"
            @click="emit('open-settings'); close()"
          >
            <i class="pi pi-cog"></i> Property Settings
          </button>
          <button
            type="button"
            class="kebab-item"
            @click="emit('open-cash-flow'); close()"
          >
            <i class="pi pi-chart-bar"></i> Cash Flow History
          </button>
          <div class="kebab-item kebab-select-item">
            <i class="pi pi-arrows-alt"></i>
            <select
              class="kebab-select"
              :value="property.llc_id"
              @change="emit('move-llc', ($event.target as HTMLSelectElement).value); close()"
            >
              <option v-for="llc in llcs" :key="llc.llc_id" :value="llc.llc_id">
                Move to: {{ llc.llc_name }}
              </option>
            </select>
          </div>
          <button
            type="button"
            class="kebab-item kebab-danger"
            @click="emit('delete'); close()"
          >
            <i class="pi pi-trash"></i> Delete Property
          </button>
        </template>
      </KebabMenu>
    </div>

    <div class="mb-3 flex items-center justify-end">
      <div class="debt-badge" :class="hasDebt ? 'debt-active' : 'debt-inactive'">
        <span>Debt to Savings</span>
        <InfoTip :text="DEBT_TO_SAVINGS_TIP" />
        <InlineEditValue
          :model-value="property.reserve_debt"
          type="number"
          currency
          :decimals="0"
          :disabled="disabled"
          class="font-bold"
          @commit="(v) => patch('reserve_debt', v)"
        />
      </div>
    </div>

    <div class="mb-1 flex items-end justify-between gap-2 rounded-xl bg-black/25 px-2 py-3">
      <BucketRing
        label="Reserve"
        theme="reserve"
        size="primary"
        :show-target-row="false"
        secondary-label="To Settle"
        :secondary-tip="TO_SETTLE_TIP"
        :balance="property.reserve_bucket_balance"
        :target="property.reserve_bucket_cap"
        :secondary-value="property.reserve_to_settle"
        :disabled="disabled"
        @update-balance="(v) => patch('reserve_bucket_balance', v)"
        @update-secondary="(v) => patch('reserve_to_settle', v)"
      />
      <div class="w-px self-stretch bg-white/[0.06]" />
      <BucketRing
        label="Tax"
        theme="tax"
        size="secondary"
        :show-target-row="false"
        secondary-label="To Settle"
        :secondary-tip="TO_SETTLE_TIP"
        :balance="property.tax_bucket_balance"
        :target="property.target_tax_allocation"
        :secondary-value="property.tax_to_settle"
        :disabled="disabled"
        @update-balance="(v) => patch('tax_bucket_balance', v)"
        @update-secondary="(v) => patch('tax_to_settle', v)"
      />
    </div>
  </div>
</template>

<style scoped>
.property-card {
  border-radius: 1rem;
  background: linear-gradient(160deg, rgba(30, 41, 59, 0.7), rgba(15, 23, 42, 0.55));
  border: 1px solid rgba(255, 255, 255, 0.07);
  padding: 1rem;
  box-shadow: 0 20px 40px -28px rgba(0, 0, 0, 0.65);
  transition: border-color 0.2s ease, transform 0.2s ease;
}

.property-card:hover {
  border-color: rgba(129, 140, 248, 0.25);
}

.kebab-item {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 0.5rem;
  border-radius: 0.5rem;
  padding: 0.5rem 0.6rem;
  font-size: 0.78rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.75);
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
  transition: background-color 0.12s ease;
}

.kebab-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.kebab-danger {
  color: #fb7185;
}

.kebab-select-item {
  padding: 0.3rem 0.6rem;
  cursor: default;
}

.kebab-select-item:hover {
  background: transparent;
}

.kebab-select {
  flex: 1;
  min-width: 0;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 0.4rem;
  color: rgba(255, 255, 255, 0.75);
  font-size: 0.74rem;
  padding: 0.25rem 0.35rem;
  outline: none;
}

.debt-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 700;
  border: 1px solid transparent;
  cursor: default;
}

.debt-active {
  background: rgba(244, 63, 94, 0.12);
  color: #fb7185;
  border-color: rgba(244, 63, 94, 0.25);
}

.debt-inactive {
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.35);
  border-color: rgba(255, 255, 255, 0.06);
}
</style>
