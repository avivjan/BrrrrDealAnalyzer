<script setup lang="ts">
import { computed } from 'vue'
import type { LLCConfiguration, PropertyStatus } from '../../types/treasury'
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

const TO_SETTLE_TIP =
  'Amount still owed to this bucket this cycle — rent allocations not yet moved or reconciled.'
const DEBT_TO_SAVINGS_TIP =
  'Reserve shortfall carried forward from prior cycles — dollars still owed back to the savings bucket.'

const RESERVE_RADIUS = 54
const RESERVE_STROKE = 9
const RESERVE_CIRCUMFERENCE = 2 * Math.PI * RESERVE_RADIUS

const reserveValue = computed(() => Number(props.property.reserve_bucket_balance))
const reserveCap = computed(() => Number(props.property.reserve_bucket_cap))
const reserveToSettle = computed(() => Number(props.property.reserve_to_settle))
const taxValue = computed(() => Number(props.property.tax_bucket_balance))
const monthlyTax = computed(() => Number(props.property.target_tax_allocation))
const taxToSettle = computed(() => Number(props.property.tax_to_settle))
const debtToSavings = computed(() => Number(props.property.reserve_debt))

const hasReserveCap = computed(() => reserveCap.value > 0)
const reserveRawPct = computed(() =>
  hasReserveCap.value ? reserveValue.value / reserveCap.value : 0,
)
const reserveFillPct = computed(() =>
  Math.min(Math.max(reserveRawPct.value, 0), 1),
)
const reserveDisplayPct = computed(() =>
  Math.round(reserveFillPct.value * 100),
)
const reserveOverflow = computed(() => hasReserveCap.value && reserveRawPct.value > 1)
const reserveNegative = computed(() => reserveValue.value < 0)
const reserveDashOffset = computed(
  () => RESERVE_CIRCUMFERENCE * (1 - reserveFillPct.value),
)

const hasMonthlyTax = computed(() => monthlyTax.value > 0)
const taxRawPct = computed(() =>
  hasMonthlyTax.value ? taxValue.value / monthlyTax.value : 0,
)
const taxFillPct = computed(() => Math.min(Math.max(taxRawPct.value, 0), 1))
const taxDisplayPct = computed(() => Math.round(taxFillPct.value * 100))
const taxOverflow = computed(() => hasMonthlyTax.value && taxRawPct.value > 1)
const taxNegative = computed(() => taxValue.value < 0)

const hasDebt = computed(() => debtToSavings.value > 0)
const gradientId = computed(() => `reserve-gauge-${props.property.property_id}`)

function patch(field: string, value: number | boolean | string) {
  emit('patch', field, value)
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}
</script>

<template>
  <article
    class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 text-slate-100 shadow-[0_24px_48px_-28px_rgba(0,0,0,0.75)] transition-[border-color,transform] duration-200 hover:border-cyan-500/25"
  >
    <!-- Header -->
    <header class="border-b border-slate-800/80 px-4 pb-3 pt-4">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0 flex-1">
          <InlineEditValue
            :model-value="property.property_name"
            :disabled="disabled"
            class="block truncate text-[0.95rem] font-semibold leading-snug text-slate-50"
            @commit="(v) => patch('property_name', v)"
          />
          <p class="mt-1 font-mono text-[0.65rem] tracking-wide text-slate-500">
            {{ property.property_id.slice(0, 8) }}…
          </p>
        </div>

        <div class="flex shrink-0 items-center gap-2">
          <div
            class="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[0.68rem] font-semibold tabular-nums"
            :class="
              hasDebt
                ? 'border-rose-500/30 bg-rose-500/10 text-rose-300'
                : 'border-slate-700 bg-slate-800/80 text-slate-400'
            "
          >
            <span class="whitespace-nowrap">Debt to Savings</span>
            <InfoTip :text="DEBT_TO_SAVINGS_TIP" />
            <InlineEditValue
              :model-value="debtToSavings"
              type="number"
              currency
              :decimals="0"
              :disabled="disabled"
              class="font-bold"
              @commit="(v) => patch('reserve_debt', v)"
            />
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
      </div>
    </header>

    <!-- Metrics body -->
    <div class="grid grid-cols-1 gap-0 sm:grid-cols-[minmax(0,1.35fr)_minmax(0,0.85fr)]">
      <!-- Reserve — hero -->
      <section class="flex flex-col items-center px-4 py-5 sm:border-r sm:border-slate-800/80">
        <p class="mb-3 text-[0.62rem] font-bold uppercase tracking-[0.14em] text-cyan-400/80">
          Reserve
        </p>

        <div class="relative h-40 w-40">
          <svg viewBox="0 0 120 120" class="h-full w-full" aria-hidden="true">
            <defs>
              <linearGradient :id="gradientId" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#22d3ee" />
                <stop offset="55%" stop-color="#06b6d4" />
                <stop offset="100%" stop-color="#0891b2" />
              </linearGradient>
              <filter :id="`${gradientId}-glow`" x="-30%" y="-30%" width="160%" height="160%">
                <feGaussianBlur stdDeviation="2.5" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            <circle
              cx="60"
              cy="60"
              :r="RESERVE_RADIUS"
              fill="none"
              stroke="rgb(30 41 59)"
              :stroke-width="RESERVE_STROKE"
            />

            <circle
              v-if="hasReserveCap"
              cx="60"
              cy="60"
              :r="RESERVE_RADIUS"
              fill="none"
              :stroke="reserveNegative ? '#fb7185' : `url(#${gradientId})`"
              :stroke-width="RESERVE_STROKE"
              stroke-linecap="round"
              :stroke-dasharray="RESERVE_CIRCUMFERENCE"
              :stroke-dashoffset="reserveDashOffset"
              :filter="reserveOverflow ? `url(#${gradientId}-glow)` : undefined"
              class="gauge-arc"
              transform="rotate(-90 60 60)"
            />
          </svg>

          <div class="absolute inset-0 flex flex-col items-center justify-center gap-0.5 px-3 text-center">
            <InlineEditValue
              :model-value="reserveValue"
              type="number"
              currency
              :decimals="0"
              :disabled="disabled"
              class="text-xl font-extrabold tracking-tight text-slate-50"
              :class="{ 'text-rose-400': reserveNegative }"
              @commit="(v) => patch('reserve_bucket_balance', Number(v))"
            />
            <p class="text-[0.62rem] font-medium text-slate-400">
              <template v-if="hasReserveCap">
                Cap {{ formatCurrency(reserveCap) }} · {{ reserveDisplayPct }}%
              </template>
              <template v-else>Cap unset</template>
            </p>
          </div>
        </div>

        <footer class="mt-4 flex w-full items-center justify-center gap-1.5 border-t border-slate-800/70 pt-3">
          <span class="text-xs text-slate-400">To Settle</span>
          <InfoTip :text="TO_SETTLE_TIP" />
          <InlineEditValue
            :model-value="reserveToSettle"
            type="number"
            currency
            :decimals="0"
            :disabled="disabled"
            class="text-sm font-semibold text-slate-100"
            @commit="(v) => patch('reserve_to_settle', Number(v))"
          />
        </footer>
      </section>

      <!-- Tax — secondary -->
      <section class="flex flex-col px-4 py-5">
        <p class="mb-3 text-[0.62rem] font-bold uppercase tracking-[0.14em] text-amber-400/85">
          Tax Liability
        </p>

        <div class="rounded-xl border border-slate-800 bg-slate-950/70 p-3.5">
          <div class="flex items-end justify-between gap-2">
            <div>
              <p class="text-[0.62rem] font-medium uppercase tracking-wide text-slate-500">Balance</p>
              <InlineEditValue
                :model-value="taxValue"
                type="number"
                currency
                :decimals="0"
                :disabled="disabled"
                class="mt-0.5 text-lg font-bold"
                :class="taxNegative ? 'text-rose-400' : 'text-amber-300'"
                @commit="(v) => patch('tax_bucket_balance', Number(v))"
              />
            </div>
            <div class="text-right">
              <p class="text-[0.62rem] font-medium uppercase tracking-wide text-slate-500">Monthly</p>
              <p class="mt-0.5 text-sm font-semibold tabular-nums text-slate-300">
                {{ hasMonthlyTax ? formatCurrency(monthlyTax) : 'Unset' }}
              </p>
            </div>
          </div>

          <div class="mt-4">
            <div class="mb-1.5 flex items-center justify-between text-[0.62rem] text-slate-500">
              <span>Funded vs monthly tax</span>
              <span class="font-semibold tabular-nums text-amber-300/90">{{ taxDisplayPct }}%</span>
            </div>
            <div class="h-2 overflow-hidden rounded-full bg-slate-800">
              <div
                class="tax-bar h-full rounded-full transition-[width] duration-700 ease-out"
                :class="
                  taxNegative
                    ? 'bg-rose-500'
                    : taxOverflow
                      ? 'bg-gradient-to-r from-amber-400 via-orange-400 to-rose-400'
                      : 'bg-gradient-to-r from-amber-500 to-orange-500'
                "
                :style="{ width: `${taxFillPct * 100}%` }"
              />
            </div>
          </div>
        </div>

        <footer class="mt-auto flex items-center gap-1.5 border-t border-slate-800/70 pt-3">
          <span class="text-xs text-slate-400">To Settle</span>
          <InfoTip :text="TO_SETTLE_TIP" />
          <InlineEditValue
            :model-value="taxToSettle"
            type="number"
            currency
            :decimals="0"
            :disabled="disabled"
            class="text-sm font-semibold text-slate-100"
            @commit="(v) => patch('tax_to_settle', Number(v))"
          />
        </footer>
      </section>
    </div>
  </article>
</template>

<style scoped>
.gauge-arc {
  transition: stroke-dashoffset 0.9s cubic-bezier(0.22, 1, 0.36, 1);
}

.tax-bar {
  box-shadow: 0 0 12px rgba(245, 158, 11, 0.35);
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
</style>
