<script setup lang="ts">
import { computed, ref } from 'vue'
import { useTreasuryStore } from '../../stores/treasuryStore'
import type { LLCConfiguration, PropertyCashFlowHistory, PropertyStatus, PropertyStatusUpdate } from '../../types/treasury'
import InlineEditValue from './InlineEditValue.vue'
import InfoTip from './InfoTip.vue'
import KebabMenu from './KebabMenu.vue'

const props = defineProps<{
  property: PropertyStatus
  llcs: LLCConfiguration[]
  disabled?: boolean
}>()

const emit = defineEmits<{
  delete: []
  'open-cash-flow': []
  'open-settings': []
  'move-llc': [llcId: string]
  'save-error': [field: string]
}>()

const store = useTreasuryStore()
const activeTab = ref<'reserve' | 'cashflow'>('reserve')
const cashFlowRange = ref<'ytd' | 'last_month' | 'all'>('ytd')
const saving = ref(false)

const TO_SETTLE_TIP =
  'Amount still owed to this bucket this cycle — rent allocations not yet moved or reconciled.'
const DEBT_TO_SAVINGS_TIP =
  'Reserve shortfall carried forward from prior cycles — dollars still owed back to the savings bucket.'

const RESERVE_RADIUS = 54
const RESERVE_STROKE = 9
const RESERVE_CIRCUMFERENCE = 2 * Math.PI * RESERVE_RADIUS

const liveProperty = computed(() =>
  store.properties.find((p) => p.property_id === props.property.property_id) ?? props.property,
)

const reserveValue = computed(() => Number(liveProperty.value.reserve_bucket_balance))
const reserveCap = computed(() => Number(liveProperty.value.reserve_bucket_cap))
const reserveToSettle = computed(() => Number(liveProperty.value.reserve_to_settle))
const taxValue = computed(() => Number(liveProperty.value.tax_bucket_balance))
const monthlyTax = computed(() => Number(liveProperty.value.target_tax_allocation))
const taxToSettle = computed(() => Number(liveProperty.value.tax_to_settle))
const debtToSavings = computed(() => Number(liveProperty.value.reserve_debt))

const hasReserveCap = computed(() => reserveCap.value > 0)
const reserveRawPct = computed(() =>
  hasReserveCap.value ? reserveValue.value / reserveCap.value : 0,
)
const reserveFillPct = computed(() => Math.min(Math.max(reserveRawPct.value, 0), 1))
const reserveDisplayPct = computed(() => Math.round(reserveFillPct.value * 100))
const reserveOverflow = computed(() => hasReserveCap.value && reserveRawPct.value > 1)
const reserveNegative = computed(() => reserveValue.value < 0)
const reserveDashOffset = computed(() => RESERVE_CIRCUMFERENCE * (1 - reserveFillPct.value))

const hasMonthlyTax = computed(() => monthlyTax.value > 0)
const taxRawPct = computed(() => (hasMonthlyTax.value ? taxValue.value / monthlyTax.value : 0))
const taxFillPct = computed(() => Math.min(Math.max(taxRawPct.value, 0), 1))
const taxDisplayPct = computed(() => Math.round(taxFillPct.value * 100))
const taxOverflow = computed(() => hasMonthlyTax.value && taxRawPct.value > 1)
const taxNegative = computed(() => taxValue.value < 0)

const hasDebt = computed(() => debtToSavings.value > 0)
const gradientId = computed(() => `reserve-gauge-${props.property.property_id}`)
const fieldDisabled = computed(() => props.disabled || saving.value)

const propertyHistory = computed(() =>
  store.cashFlowHistory
    .filter((row) => row.property_id === props.property.property_id)
    .sort((a, b) => a.month_year.localeCompare(b.month_year)),
)

const filteredCashFlow = computed(() => {
  const rows = propertyHistory.value
  if (cashFlowRange.value === 'all') return rows

  const now = new Date()
  if (cashFlowRange.value === 'last_month') {
    const d = new Date(now.getFullYear(), now.getMonth() - 1, 1)
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    return rows.filter((row) => row.month_year === key)
  }

  const yearPrefix = String(now.getFullYear())
  return rows.filter((row) => row.month_year.startsWith(yearPrefix))
})

const periodMonthlyTotal = computed(() =>
  filteredCashFlow.value.reduce((sum, row) => sum + Number(row.monthly_cash_flow), 0),
)

const periodLatestCumulative = computed(() => {
  const rows = filteredCashFlow.value
  const last = rows[rows.length - 1]
  if (!last) return 0
  return Number(last.cumulative_cash_flow)
})

const cashFlowRangeLabel = computed(() => {
  if (cashFlowRange.value === 'ytd') return 'Year to date'
  if (cashFlowRange.value === 'last_month') return 'Last month'
  return 'All time'
})

async function patchField(field: keyof PropertyStatusUpdate | 'property_name', value: number | boolean | string) {
  if (fieldDisabled.value) return
  saving.value = true
  try {
    await store.patchProperty(props.property.property_id, { [field]: value } as PropertyStatusUpdate)
  } catch {
    emit('save-error', field)
  } finally {
    saving.value = false
  }
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

function formatSignedCurrency(value: number): string {
  const formatted = formatCurrency(Math.abs(value))
  if (value > 0) return `+${formatted}`
  if (value < 0) return `-${formatted}`
  return formatted
}

function rowTone(row: PropertyCashFlowHistory): string {
  const n = Number(row.monthly_cash_flow)
  if (n > 0) return 'text-emerald-300'
  if (n < 0) return 'text-rose-400'
  return 'text-slate-300'
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
            :model-value="liveProperty.property_name"
            :disabled="fieldDisabled"
            class="block truncate text-[0.95rem] font-semibold leading-snug text-slate-50"
            @commit="(v) => patchField('property_name', v)"
          />
          <p class="mt-1 font-mono text-[0.65rem] tracking-wide text-slate-500">
            {{ liveProperty.property_id.slice(0, 8) }}…
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
              :disabled="fieldDisabled"
              class="font-bold"
              @commit="(v) => patchField('reserve_debt', Number(v))"
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
              <div class="kebab-item kebab-select-item">
                <i class="pi pi-arrows-alt"></i>
                <select
                  class="kebab-select"
                  :value="liveProperty.llc_id"
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

    <!-- Tabs -->
    <div class="flex border-b border-slate-800/80 px-4">
      <button
        type="button"
        class="tab-btn"
        :class="activeTab === 'reserve' ? 'tab-btn-active' : 'tab-btn-idle'"
        @click="activeTab = 'reserve'"
      >
        Reserve
      </button>
      <button
        type="button"
        class="tab-btn"
        :class="activeTab === 'cashflow' ? 'tab-btn-active' : 'tab-btn-idle'"
        @click="activeTab = 'cashflow'"
      >
        Cash Flow
      </button>
    </div>

    <!-- Reserve tab -->
    <div v-if="activeTab === 'reserve'" class="grid grid-cols-1 gap-0 sm:grid-cols-[minmax(0,1.35fr)_minmax(0,0.85fr)]">
      <section class="flex flex-col items-center px-4 py-5 sm:border-r sm:border-slate-800/80">
        <p class="mb-3 text-[0.62rem] font-bold uppercase tracking-[0.14em] text-cyan-400/80">
          Reserve
        </p>

        <div class="relative h-40 w-40">
          <svg viewBox="0 0 120 120" class="pointer-events-none h-full w-full" aria-hidden="true">
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
              :disabled="fieldDisabled"
              class="text-xl font-extrabold tracking-tight text-slate-50"
              :class="{ 'text-rose-400': reserveNegative }"
              @commit="(v) => patchField('reserve_bucket_balance', Number(v))"
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
            :disabled="fieldDisabled"
            class="text-sm font-semibold text-slate-100"
            @commit="(v) => patchField('reserve_to_settle', Number(v))"
          />
        </footer>
      </section>

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
                :disabled="fieldDisabled"
                class="mt-0.5 text-lg font-bold"
                :class="taxNegative ? 'text-rose-400' : 'text-amber-300'"
                @commit="(v) => patchField('tax_bucket_balance', Number(v))"
              />
            </div>
            <div class="text-right">
              <p class="text-[0.62rem] font-medium uppercase tracking-wide text-slate-500">Monthly Tax</p>
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
            :disabled="fieldDisabled"
            class="text-sm font-semibold text-slate-100"
            @commit="(v) => patchField('tax_to_settle', Number(v))"
          />
        </footer>
      </section>
    </div>

    <!-- Cash Flow tab -->
    <div v-else class="px-4 py-4">
      <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div class="flex flex-wrap gap-1.5">
          <button
            type="button"
            class="range-chip"
            :class="cashFlowRange === 'ytd' ? 'range-chip-active' : 'range-chip-idle'"
            @click="cashFlowRange = 'ytd'"
          >
            Start of year
          </button>
          <button
            type="button"
            class="range-chip"
            :class="cashFlowRange === 'last_month' ? 'range-chip-active' : 'range-chip-idle'"
            @click="cashFlowRange = 'last_month'"
          >
            Last month
          </button>
          <button
            type="button"
            class="range-chip"
            :class="cashFlowRange === 'all' ? 'range-chip-active' : 'range-chip-idle'"
            @click="cashFlowRange = 'all'"
          >
            All time
          </button>
        </div>
        <button type="button" class="history-btn" @click="emit('open-cash-flow')">
          <i class="pi pi-external-link"></i>
          Cash Flow History
        </button>
      </div>

      <div class="mb-4 grid grid-cols-2 gap-3">
        <div class="cf-stat">
          <p class="cf-stat-label">{{ cashFlowRangeLabel }} · Monthly total</p>
          <p
            class="cf-stat-value"
            :class="periodMonthlyTotal >= 0 ? 'text-emerald-300' : 'text-rose-400'"
          >
            {{ formatSignedCurrency(periodMonthlyTotal) }}
          </p>
        </div>
        <div class="cf-stat">
          <p class="cf-stat-label">Latest cumulative</p>
          <p
            class="cf-stat-value"
            :class="periodLatestCumulative >= 0 ? 'text-slate-100' : 'text-rose-400'"
          >
            {{ formatCurrency(periodLatestCumulative) }}
          </p>
        </div>
      </div>

      <div v-if="filteredCashFlow.length === 0" class="cf-empty">
        No cash-flow snapshots for this period.
      </div>
      <div v-else class="cf-table-wrap">
        <table class="cf-table">
          <thead>
            <tr>
              <th>Month</th>
              <th>Monthly</th>
              <th>Cumulative</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredCashFlow" :key="row.history_id">
              <td class="font-medium text-slate-300">{{ row.month_year }}</td>
              <td class="font-semibold tabular-nums" :class="rowTone(row)">
                {{ formatSignedCurrency(Number(row.monthly_cash_flow)) }}
              </td>
              <td class="font-semibold tabular-nums text-slate-300">
                {{ formatCurrency(Number(row.cumulative_cash_flow)) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
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

.tab-btn {
  position: relative;
  padding: 0.65rem 0.9rem;
  font-size: 0.78rem;
  font-weight: 700;
  background: transparent;
  border: none;
  cursor: pointer;
  transition: color 0.15s ease;
}

.tab-btn-idle {
  color: rgba(148, 163, 184, 0.75);
}

.tab-btn-idle:hover {
  color: rgba(226, 232, 240, 0.9);
}

.tab-btn-active {
  color: #e2e8f0;
}

.tab-btn-active::after {
  content: '';
  position: absolute;
  left: 0.65rem;
  right: 0.65rem;
  bottom: 0;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, #22d3ee, #06b6d4);
}

.range-chip {
  padding: 0.35rem 0.65rem;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 700;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.range-chip-idle {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.08);
  color: rgba(148, 163, 184, 0.85);
}

.range-chip-idle:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e8f0;
}

.range-chip-active {
  background: rgba(99, 102, 241, 0.15);
  border-color: rgba(99, 102, 241, 0.35);
  color: #c7d2fe;
}

.history-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 0.75rem;
  border-radius: 0.55rem;
  background: rgba(16, 185, 129, 0.12);
  border: 1px solid rgba(16, 185, 129, 0.28);
  color: #6ee7b7;
  font-size: 0.72rem;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.history-btn:hover {
  background: rgba(16, 185, 129, 0.2);
}

.cf-stat {
  border-radius: 0.75rem;
  border: 1px solid rgb(30 41 59);
  background: rgba(2, 6, 23, 0.55);
  padding: 0.75rem;
}

.cf-stat-label {
  margin: 0;
  font-size: 0.62rem;
  font-weight: 600;
  uppercase: none;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: rgb(100 116 139);
}

.cf-stat-value {
  margin: 0.25rem 0 0;
  font-size: 1rem;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.cf-empty {
  padding: 2rem 0;
  text-align: center;
  font-size: 0.78rem;
  color: rgba(148, 163, 184, 0.65);
}

.cf-table-wrap {
  overflow-x: auto;
  border-radius: 0.75rem;
  border: 1px solid rgb(30 41 59);
}

.cf-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.76rem;
}

.cf-table thead th {
  text-align: left;
  padding: 0.55rem 0.65rem;
  font-size: 0.6rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: rgb(100 116 139);
  background: rgba(15, 23, 42, 0.8);
  border-bottom: 1px solid rgb(30 41 59);
}

.cf-table tbody td {
  padding: 0.55rem 0.65rem;
  border-bottom: 1px solid rgba(30, 41, 59, 0.65);
}

.cf-table tbody tr:last-child td {
  border-bottom: none;
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
