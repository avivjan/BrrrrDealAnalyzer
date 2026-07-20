<script setup lang="ts">
import { computed } from 'vue'
import type { LLCConfiguration, PropertyStatus } from '../../types/treasury'
import BucketRing from './BucketRing.vue'
import InlineEditValue from './InlineEditValue.vue'
import ToggleSwitch from './ToggleSwitch.vue'
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
  'move-llc': [llcId: string]
}>()

function prettifyId(id: string): string {
  if (id.length > 24 && !/[-_]/.test(id)) return id
  return id
    .replace(/[-_]+/g, ' ')
    .split(' ')
    .filter(Boolean)
    .map((word) => (/^[a-zA-Z]/.test(word) ? word[0]!.toUpperCase() + word.slice(1) : word))
    .join(' ')
}

const title = computed(() => prettifyId(props.property.property_id))
const hasDebt = computed(() => props.property.reserve_debt > 0)

function patch(field: string, value: number | boolean | string) {
  emit('patch', field, value)
}
</script>

<template>
  <div class="property-card">
    <div class="mb-3 flex items-start justify-between gap-2">
      <div class="min-w-0">
        <h3 class="truncate text-[0.95rem] font-bold text-white">{{ title }}</h3>
        <code class="text-[0.65rem] text-white/30">{{ property.property_id }}</code>
      </div>
      <KebabMenu>
        <template #default="{ close }">
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

    <div class="mb-4 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[0.72rem]">
      <div class="flex items-center gap-1">
        <span class="text-white/35">Rent Target</span>
        <InlineEditValue
          :model-value="property.base_rent_target"
          type="number"
          currency
          :decimals="0"
          :disabled="disabled"
          class="font-bold text-emerald-300"
          @commit="(v) => patch('base_rent_target', v)"
        />
      </div>
      <div class="flex items-center gap-1">
        <span class="text-white/35">Reserve Target</span>
        <InlineEditValue
          :model-value="property.target_reserve_allocation"
          type="number"
          currency
          :decimals="0"
          :disabled="disabled"
          class="font-semibold text-violet-300"
          @commit="(v) => patch('target_reserve_allocation', v)"
        />
      </div>
      <div class="flex items-center gap-1">
        <span class="text-white/35">Interest Earned</span>
        <InlineEditValue
          :model-value="property.interest_earned_counter"
          type="number"
          currency
          :decimals="4"
          :disabled="disabled"
          class="font-semibold text-cyan-300"
          @commit="(v) => patch('interest_earned_counter', v)"
        />
      </div>
      <div class="debt-badge" :class="hasDebt ? 'debt-active' : 'debt-inactive'">
        <i class="pi pi-exclamation-circle text-[0.6rem]"></i>
        <span>Debt</span>
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

    <div class="mb-4 flex items-stretch justify-between gap-1 rounded-xl bg-black/25 px-2 py-3">
      <BucketRing
        label="Tax"
        theme="tax"
        target-label="Target"
        secondary-label="To Settle"
        :balance="property.tax_bucket_balance"
        :target="property.target_tax_allocation"
        :secondary-value="property.tax_to_settle"
        :disabled="disabled"
        @update-balance="(v) => patch('tax_bucket_balance', v)"
        @update-target="(v) => patch('target_tax_allocation', v)"
        @update-secondary="(v) => patch('tax_to_settle', v)"
      />
      <div class="w-px bg-white/[0.06]" />
      <BucketRing
        label="Insurance"
        theme="insurance"
        target-label="Target"
        secondary-label="To Settle"
        :balance="property.ins_bucket_balance"
        :target="property.target_ins_allocation"
        :secondary-value="property.ins_to_settle"
        :disabled="disabled"
        @update-balance="(v) => patch('ins_bucket_balance', v)"
        @update-target="(v) => patch('target_ins_allocation', v)"
        @update-secondary="(v) => patch('ins_to_settle', v)"
      />
      <div class="w-px bg-white/[0.06]" />
      <BucketRing
        label="Reserve"
        theme="reserve"
        target-label="Cap"
        secondary-label="To Settle"
        :balance="property.reserve_bucket_balance"
        :target="property.reserve_bucket_cap"
        :secondary-value="property.reserve_to_settle"
        :disabled="disabled"
        @update-balance="(v) => patch('reserve_bucket_balance', v)"
        @update-target="(v) => patch('reserve_bucket_cap', v)"
        @update-secondary="(v) => patch('reserve_to_settle', v)"
      />
    </div>

    <div class="flex flex-col gap-2 border-t border-white/[0.06] pt-3">
      <label class="flex items-center justify-between gap-2">
        <span class="text-[0.72rem] font-medium text-white/65">Force Tax/Ins Accrual</span>
        <ToggleSwitch
          :model-value="property.force_tax_ins_accrual"
          :disabled="disabled"
          @update:model-value="(v) => patch('force_tax_ins_accrual', v)"
        />
      </label>
      <label class="flex items-center justify-between gap-2">
        <span class="text-[0.72rem] font-medium text-white/65">Double Reserve On Recovery</span>
        <ToggleSwitch
          :model-value="property.double_reserve_on_recovery"
          :disabled="disabled"
          @update:model-value="(v) => patch('double_reserve_on_recovery', v)"
        />
      </label>
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
