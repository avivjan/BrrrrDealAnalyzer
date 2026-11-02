<script setup lang="ts">
/**
 * "Import to liquidity" (and "Review changes" / Re-sync): one deal at a time, the current timeline vs with the deal
 * (a dashed line), the insights, and the before -> after list. Nothing is imported until "Import" is pressed
 * (tasks/todo/DealCashInLiquidity.md, decision 11). Re-importing is the same call, so this modal also confirms a
 * deal edit's changes.
 */
import { computed, onMounted, ref } from 'vue'

import { useLiquidityStore } from '../../stores/liquidityStore'
import type { DealCashRowChanges, LiquidityDealBoard, UseDealValueForField } from '../../types/liquidity'
import { buildDealImportInsights } from '../../utils/dealCashRowsPreview'
import { todayISO } from '../../utils/liquidityEngine'
import { formatMoney } from '../../utils/money'
import UiButton from '../ui/UiButton.vue'
import UiModalPanel from '../ui/UiModalPanel.vue'
import DealCashRowChangesList from './DealCashRowChangesList.vue'
import TimelineChart from './TimelineChart.vue'

const props = defineProps<{
  dealBoard: LiquidityDealBoard
  dealId: string
  dealAddress: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'imported', result: DealCashRowChanges): void
}>()

const liquidityStore = useLiquidityStore()
const preview = ref<DealCashRowChanges | null>(null)
const useDealValueFor = ref<UseDealValueForField[]>([])
const loadingPreview = ref(true)
const importing = ref(false)
const errorMessage = ref<string | null>(null)

async function loadPreview() {
  loadingPreview.value = true
  errorMessage.value = null
  try {
    // The timeline must be loaded to draw "without the deal" (the modal can open from a deal board).
    if (liquidityStore.transactions.length === 0 && liquidityStore.recurringRules.length === 0) await liquidityStore.fetchAll()
    preview.value = await liquidityStore.previewDealImport(props.dealBoard, props.dealId, useDealValueFor.value)
  } catch (error: any) {
    errorMessage.value = error?.response?.data?.detail || error?.message || 'Could not load the preview'
  } finally {
    loadingPreview.value = false
  }
}
onMounted(loadPreview)

function onUseDealValueForChanged(choices: UseDealValueForField[]) {
  useDealValueFor.value = choices
  void loadPreview()
}

const isAlreadyImported = computed(() => (preview.value?.changes ?? []).some(change => change.transaction_id !== null))
const rowCountThatChanges = computed(() => {
  const counts = preview.value?.change_counts
  return counts ? counts.added + counts.updated + counts.removed + counts.kept_no_longer_in_the_deal : 0
})

const seriesPair = computed(() => preview.value ? liquidityStore.seriesWithAndWithoutDealChanges(preview.value.changes) : null)
const insights = computed(() => {
  if (!preview.value || !seriesPair.value) return null
  return buildDealImportInsights(seriesPair.value.seriesWithoutTheDeal, seriesPair.value.seriesWithTheDeal,
    preview.value.changes, liquidityStore.settings.reserve_dollars, todayISO())
})

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
function shortDate(isoDate: string | null): string {
  if (!isoDate) return '—'
  const [year, month, day] = isoDate.split('-')
  return `${MONTHS[Number(month) - 1] ?? ''} ${Number(day)}, ${year}`
}
function monthLabel(yearMonth: string): string {
  const [year, month] = yearMonth.split('-')
  return `${MONTHS[Number(month) - 1] ?? ''} ${year}`
}

async function confirmImport() {
  importing.value = true
  errorMessage.value = null
  try {
    const result = await liquidityStore.importDeal(props.dealBoard, props.dealId, useDealValueFor.value)
    emit('imported', result)
    emit('close')
  } catch (error: any) {
    errorMessage.value = error?.response?.data?.detail || error?.message || 'The import failed'
  } finally {
    importing.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div data-testid="deal-import-preview" class="fixed inset-0 z-50 flex items-center justify-center p-4" @keydown.esc="emit('close')">
      <div class="absolute inset-0 bg-fg/50 md:backdrop-blur-sm" @click="emit('close')" />
      <UiModalPanel size="xl" labelled-by="deal-import-preview-title" class="relative">
        <template #header>
          <div class="flex items-start justify-between gap-3">
            <div>
              <h2 id="deal-import-preview-title" class="font-display text-lg font-semibold tracking-display text-fg">
                {{ isAlreadyImported ? 'Re-sync with liquidity' : 'Import to liquidity' }}
              </h2>
              <p class="text-sm text-fg-muted">{{ dealAddress }} · Cash Needed rows (Lowest ARV)</p>
            </div>
            <button type="button" aria-label="Close" class="text-fg-muted" @click="emit('close')"><i class="pi pi-times"></i></button>
          </div>
        </template>

        <p v-if="loadingPreview && !preview" class="text-sm text-fg-muted">Loading the preview…</p>
        <p v-if="errorMessage" data-testid="deal-import-preview.error" class="text-sm text-negative">{{ errorMessage }}</p>

        <template v-if="preview && seriesPair && insights">
          <div class="h-56">
            <TimelineChart
              :days="seriesPair.seriesWithoutTheDeal.days"
              :global-min="seriesPair.seriesWithoutTheDeal.globalMin"
              :global-min-dates="seriesPair.seriesWithoutTheDeal.globalMinDates"
              :first-negative-date="seriesPair.seriesWithoutTheDeal.firstNegativeDate"
              :reserve-dollars="liquidityStore.settings.reserve_dollars"
              :balances-with-the-deal="seriesPair.seriesWithTheDeal.days.map(day => day.balance_dollars)"
            />
          </div>
          <p class="mt-1 text-xs text-fg-muted">Solid: today's timeline. Dashed: with this deal.</p>

          <dl data-testid="deal-import-preview.insights" class="mt-3 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
            <div data-insight="lowest-balance">
              <dt class="text-fg-muted">Lowest balance</dt>
              <dd class="tabular-nums text-fg">
                {{ formatMoney(insights.lowestBalanceWithoutTheDeal.amountDollars) }} → <strong :class="insights.lowestBalanceWithTheDeal.amountDollars < 0 ? 'text-negative' : ''">{{ formatMoney(insights.lowestBalanceWithTheDeal.amountDollars) }}</strong>
                on {{ shortDate(insights.lowestBalanceWithTheDeal.date) }}
              </dd>
            </div>
            <div data-insight="below-reserve">
              <dt class="text-fg-muted">Below the reserve ({{ formatMoney(liquidityStore.settings.reserve_dollars) }})</dt>
              <dd class="text-fg">
                <template v-if="insights.daysBelowReserveWithTheDeal > 0">{{ insights.daysBelowReserveWithTheDeal }} days, from {{ shortDate(insights.firstDateBelowReserveWithTheDeal) }}</template>
                <template v-else>Never</template>
              </dd>
            </div>
            <div data-insight="first-negative">
              <dt class="text-fg-muted">First negative day</dt>
              <dd :class="insights.firstNegativeDateWithTheDeal ? 'text-negative font-semibold' : 'text-fg'">{{ insights.firstNegativeDateWithTheDeal ? shortDate(insights.firstNegativeDateWithTheDeal) : 'None' }}</dd>
            </div>
            <div data-insight="deal-totals">
              <dt class="text-fg-muted">The deal's money out / in</dt>
              <dd class="tabular-nums text-fg">{{ formatMoney(insights.dealMoneyOutDollars) }} out · {{ formatMoney(insights.dealMoneyInDollars) }} in</dd>
            </div>
            <div data-insight="largest-day">
              <dt class="text-fg-muted">Largest single-day outflow</dt>
              <dd class="tabular-nums text-fg">
                <template v-if="insights.largestSingleDayOutflowOfTheDeal">{{ formatMoney(insights.largestSingleDayOutflowOfTheDeal.amountDollars) }} on {{ shortDate(insights.largestSingleDayOutflowOfTheDeal.date) }}</template>
                <template v-else>None</template>
              </dd>
            </div>
            <div data-insight="next-30-days">
              <dt class="text-fg-muted">Cash today vs the deal's next 30 days</dt>
              <dd class="tabular-nums text-fg">{{ formatMoney(insights.cashTodayDollars) }} vs {{ formatMoney(insights.dealMoneyOutInTheNext30DaysDollars) }} out</dd>
            </div>
            <div data-insight="recovery">
              <dt class="text-fg-muted">Back above the reserve after the refi ({{ shortDate(insights.lastDealRowDate) }})</dt>
              <dd class="text-fg">{{ insights.dateBackAtOrAboveReserveAfterTheLastDealRow ? shortDate(insights.dateBackAtOrAboveReserveAfterTheLastDealRow) : 'Not in the timeline' }}</dd>
            </div>
          </dl>

          <div data-testid="deal-import-preview.by-month" class="mt-3 flex flex-wrap gap-2 text-xs">
            <span v-for="month in insights.dealRowsByMonth" :key="month.month" class="rounded-ctl bg-surface-2 px-2 py-1 tabular-nums text-fg-muted">
              {{ monthLabel(month.month) }}: {{ month.rowCount }} rows, {{ formatMoney(month.netDollars) }}
            </span>
          </div>

          <h3 class="mt-4 text-sm font-semibold text-fg">{{ rowCountThatChanges }} row{{ rowCountThatChanges === 1 ? '' : 's' }} change</h3>
          <DealCashRowChangesList
            class="mt-2"
            :changes="preview.changes"
            :use-deal-value-for="useDealValueFor"
            @update:use-deal-value-for="onUseDealValueForChanged"
          />
        </template>

        <template #footer>
          <div class="flex justify-end gap-2">
            <UiButton variant="ghost" @click="emit('close')">Cancel</UiButton>
            <UiButton data-testid="deal-import-preview.confirm" :loading="importing" :disabled="!preview || importing" @click="confirmImport">
              {{ isAlreadyImported ? `Re-sync ${rowCountThatChanges} rows` : `Import ${preview?.change_counts.added ?? 0} rows` }}
            </UiButton>
          </div>
        </template>
      </UiModalPanel>
    </div>
  </Teleport>
</template>
