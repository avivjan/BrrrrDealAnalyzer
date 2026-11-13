<script setup lang="ts">
/**
 * "Import to liquidity", and "Review changes" on an imported deal, as a full-screen decision view
 * (tasks/todo/DealImpactSimulator.md): the theater's look, a verdict first, the chart of the timeline before vs
 * after, three insight cards, and the details (by month, the rows) on demand. Nothing is imported until the primary
 * button is pressed (tasks/todo/DealCashInLiquidity.md, decision 11). Re-importing is the same call, so this view
 * also confirms a deal edit's changes; it then compares "Now" with "After these changes".
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import { useInjectedDealAttributionLookup } from '../../../composables/useLiquidityDealAttribution'
import { resolvedTheme } from '../../../design/theme'
import { useLiquidityStore } from '../../../stores/liquidityStore'
import type { DealCashRowChanges, LiquidityDealBoard, UseDealValueForField } from '../../../types/liquidity'
import { buildDealImpactDecision, formatDecisionDate } from '../../../utils/dealImpactDecision'
import { todayISO } from '../../../utils/liquidityEngine'
import { formatMoney, formatSignedMoney } from '../../../utils/money'
import DealCashRowChangesList from '../DealCashRowChangesList.vue'
import { assignDealColorSlotByDealKey, dealColorHexForSlot, dealKeyOf } from '../dealColors'
import DealImpactChart, { type DealRowOnADay } from './DealImpactChart.vue'

import { dealOnTheLiquidityTimeline } from '../../../navigation/appLinks'
import { useLiquidityTimelineChangePromptStore } from '../../../stores/liquidityTimelineChangePromptStore'

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
const todayIsoDate = todayISO()

async function loadPreview() {
  loadingPreview.value = true
  errorMessage.value = null
  try {
    // The timeline must be loaded to draw "before" (the view can open from a deal board).
    if (liquidityStore.transactions.length === 0 && liquidityStore.recurringRules.length === 0) await liquidityStore.fetchAll()
    preview.value = await liquidityStore.previewDealImport(props.dealBoard, props.dealId, useDealValueFor.value)
  } catch (error: any) {
    errorMessage.value = error?.response?.data?.detail || error?.message || 'Could not load the preview'
  } finally {
    loadingPreview.value = false
  }
}

function onUseDealValueForChanged(choices: UseDealValueForField[]) {
  useDealValueFor.value = choices
  void loadPreview()
}

/** An imported deal: the view reviews its changes (a re-sync) rather than a new import. */
const isAlreadyImported = computed(() => (preview.value?.changes ?? []).some(change => change.transaction_id !== null))
const mode = computed(() => (isAlreadyImported.value ? 'resync' : 'import'))
const rowCountThatChanges = computed(() => {
  const counts = preview.value?.change_counts
  return counts ? counts.added + counts.updated + counts.removed + counts.kept_no_longer_in_the_deal : 0
})
const beforeLabel = computed(() => (mode.value === 'import' ? 'Current' : 'Now'))
const afterLabel = computed(() => (mode.value === 'import' ? 'With this deal' : 'After these changes'))

const seriesPair = computed(() => preview.value ? liquidityStore.seriesWithAndWithoutDealChanges(preview.value.changes) : null)
const decision = computed(() => {
  if (!preview.value || !seriesPair.value) return null
  return buildDealImpactDecision({
    seriesBefore: seriesPair.value.seriesWithoutTheDeal,
    seriesAfter: seriesPair.value.seriesWithTheDeal,
    changes: preview.value.changes,
    keyDates: preview.value.key_dates ?? [],
    reserveDollars: liquidityStore.settings.reserve_dollars,
    todayIsoDate,
    mode: mode.value,
  })
})

/** The deal's colour: the legend's, or (opened from a deal board) the one it will get once imported. */
const dealAttributionLookup = useInjectedDealAttributionLookup()
const dealColorHex = computed(() => {
  const dealKey = dealKeyOf(props.dealBoard, props.dealId)
  const fromTheLegend = dealAttributionLookup?.value.attributionForDealKey(dealKey)?.dealColorHex
  if (fromTheLegend) return fromTheLegend
  const dealKeys = [...liquidityStore.importedDeals.map(deal => dealKeyOf(deal.deal_board, deal.deal_id)), dealKey]
  return dealColorHexForSlot(assignDealColorSlotByDealKey(dealKeys).get(dealKey) ?? null, resolvedTheme.value)
})

/** The deal's rows by date (after the change), for the chart's tooltip. */
const dealRowsByDate = computed<Record<string, DealRowOnADay[]>>(() => {
  const rowsByDate: Record<string, DealRowOnADay[]> = {}
  for (const change of preview.value?.changes ?? []) {
    if (change.change_kind === 'removed' || change.change_kind === 'kept_done' || !change.date_after || change.amount_dollars_after === null) continue
    const countedOn = change.date_after < todayIsoDate && change.amount_dollars_after < 0 ? todayIsoDate : change.date_after
    ;(rowsByDate[countedOn] ??= []).push({ description: change.description, amountDollars: change.amount_dollars_after })
  }
  return rowsByDate
})

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
function monthLabel(yearMonth: string): string {
  const [year, month] = yearMonth.split('-')
  return `${MONTHS[Number(month) - 1] ?? ''} '${year?.slice(2)}`
}
const money = (dollars: number) => formatMoney(Math.round(dollars))

const VERDICT_STYLE = {
  negative: { box: 'border-negative/40 bg-negative/10', icon: 'pi pi-times-circle text-negative', title: 'Goes negative' },
  warning: { box: 'border-warning/50 bg-warning/10', icon: 'pi pi-exclamation-triangle text-warning', title: 'Dips under your reserve' },
  positive: { box: 'border-positive/40 bg-positive/10', icon: 'pi pi-check-circle text-positive', title: 'Stays safe' },
} as const
const verdictStyle = computed(() => VERDICT_STYLE[decision.value?.tone ?? 'positive'])

/** The deal's net per month as small bars. */
const monthBars = computed(() => {
  const months = decision.value?.insights.dealRowsByMonth ?? []
  const largest = months.reduce((most, month) => Math.max(most, Math.abs(month.netDollars)), 0) || 1
  return months.map(month => ({ ...month, heightPercent: Math.max(4, (Math.abs(month.netDollars) / largest) * 100) }))
})

const rowsOpen = ref(false)
const byMonthOpen = ref(false)

const primaryLabel = computed(() => {
  if (isAlreadyImported.value) return `Re-sync ${rowCountThatChanges.value} row${rowCountThatChanges.value === 1 ? '' : 's'}`
  const rowCount = preview.value?.change_counts.added ?? 0
  return decision.value?.riskLevel === 'goes_negative' ? `Import anyway · ${rowCount} rows` : `Import ${rowCount} rows`
})

async function confirmImport() {
  importing.value = true
  errorMessage.value = null
  try {
    const result = await liquidityStore.importDeal(props.dealBoard, props.dealId, useDealValueFor.value)
    // The one notice, with a link straight to this deal's rows (tasks/todo/ConstructionAccountPerRehab.md, Step C0).
    const counts = result.change_counts
    useLiquidityTimelineChangePromptStore().showTimelineUpdated(counts.added + counts.updated + counts.removed,
      dealOnTheLiquidityTimeline(props.dealBoard, props.dealId))
    emit('imported', result)
    emit('close')
  } catch (error: any) {
    errorMessage.value = error?.response?.data?.detail || error?.message || 'The import failed'
  } finally {
    importing.value = false
  }
}

// Esc closes this view first (capture phase, so a deal modal underneath does not close too).
function onKeyDown(event: KeyboardEvent) {
  if (event.key !== 'Escape') return
  event.stopPropagation()
  event.preventDefault()
  emit('close')
}
const rootRef = ref<HTMLElement | null>(null)
onMounted(async () => {
  window.addEventListener('keydown', onKeyDown, { capture: true })
  await loadPreview()
  rowsOpen.value = isAlreadyImported.value
  await nextTick()
  rootRef.value?.focus()
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown, { capture: true }))
</script>

<template>
  <Teleport to="body">
    <Transition name="deal-impact-fade" appear>
      <div
        ref="rootRef"
        data-testid="deal-import-preview"
        :data-mode="mode"
        role="dialog"
        aria-modal="true"
        aria-labelledby="deal-impact-title"
        tabindex="-1"
        class="fixed inset-0 z-50 flex flex-col overflow-hidden bg-page text-fg focus:outline-none"
      >
        <!-- Top bar -->
        <div class="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line bg-surface/85 px-3 py-2 backdrop-blur-md sm:px-5">
          <span class="h-3 w-3 shrink-0 rounded-full ring-2 ring-surface" :style="{ backgroundColor: dealColorHex }" aria-hidden="true"></span>
          <div class="min-w-0 flex-1">
            <h2 id="deal-impact-title" class="truncate font-display text-lg font-semibold tracking-display text-fg">
              {{ isAlreadyImported ? 'Re-sync with liquidity' : 'Import to liquidity' }}
            </h2>
            <p class="truncate text-xs text-fg-muted">{{ dealAddress }} · Cash Needed rows (Lowest ARV)</p>
          </div>
          <div v-if="decision" class="no-scrollbar order-last flex w-full items-center gap-2 overflow-x-auto md:order-none md:w-auto">
            <span data-testid="deal-impact.chip.cash-today" class="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border-ui border-line bg-surface px-3 py-1 shadow-1">
              <span class="text-[10px] font-semibold uppercase tracking-[0.12em] text-fg-muted">Cash today</span>
              <span class="numeric text-sm font-bold text-fg">{{ money(decision.next30Days.cashTodayDollars) }}</span>
            </span>
            <span data-testid="deal-impact.chip.deal-cash" class="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border-ui border-line bg-surface px-3 py-1 shadow-1">
              <span class="text-[10px] font-semibold uppercase tracking-[0.12em] text-fg-muted">{{ isAlreadyImported ? 'Deal' : 'This deal' }}</span>
              <span class="numeric text-sm font-bold text-negative">−{{ money(decision.dealMoneyOutDollars) }}</span>
              <span class="numeric text-sm font-bold text-positive">+{{ money(decision.dealMoneyInDollars) }}</span>
            </span>
          </div>
          <div class="hidden items-center gap-2 sm:flex">
            <UiButton variant="ghost" @click="emit('close')">Cancel</UiButton>
            <UiButton
              data-testid="deal-import-preview.confirm"
              :variant="decision?.riskLevel === 'goes_negative' && !isAlreadyImported ? 'danger' : 'primary'"
              :loading="importing"
              :disabled="!preview || importing"
              @click="confirmImport"
            >{{ primaryLabel }}</UiButton>
          </div>
          <UiIconButton data-testid="deal-impact.close" label="Close (Esc)" size="md" @click="emit('close')">
            <i class="pi pi-times text-sm" aria-hidden="true"></i>
          </UiIconButton>
        </div>

        <div class="min-h-0 flex-1 overflow-y-auto overscroll-contain lg:overflow-hidden">
          <p v-if="loadingPreview && !preview" data-testid="deal-impact.loading" class="flex h-full items-center justify-center gap-2 text-sm text-fg-muted">
            <i class="pi pi-spin pi-spinner text-primary" aria-hidden="true"></i> Projecting the deal on your timeline…
          </p>
          <p v-if="errorMessage" data-testid="deal-import-preview.error" class="m-4 rounded-card border-ui border-negative/40 bg-negative/10 px-4 py-3 text-sm text-negative">{{ errorMessage }}</p>

          <div v-if="preview && seriesPair && decision" class="flex min-h-full flex-col gap-3 p-3 sm:p-5 lg:h-full">
            <!-- The verdict -->
            <section
              data-testid="deal-impact.verdict"
              :data-risk-level="decision.riskLevel"
              class="flex items-start gap-3 rounded-card border-ui px-4 py-3"
              :class="verdictStyle.box"
            >
              <i :class="verdictStyle.icon" class="mt-0.5 text-xl" aria-hidden="true"></i>
              <div class="min-w-0">
                <p class="text-[10px] font-semibold uppercase tracking-[0.14em] text-fg-muted">{{ verdictStyle.title }}</p>
                <p data-testid="deal-impact.verdict.headline" class="text-base text-fg sm:text-lg">
                  <template v-for="(segment, position) in decision.verdictHeadline" :key="position"><strong v-if="segment.isEmphasised" class="font-semibold">{{ segment.text }}</strong><template v-else>{{ segment.text }}</template></template>
                </p>
                <p v-if="decision.verdictFollowUp" data-testid="deal-impact.verdict.follow-up" class="mt-0.5 text-sm text-fg-muted">
                  <template v-for="(segment, position) in decision.verdictFollowUp" :key="position"><strong v-if="segment.isEmphasised" class="font-semibold text-fg">{{ segment.text }}</strong><template v-else>{{ segment.text }}</template></template>
                </p>
              </div>
            </section>

            <div class="flex min-h-0 flex-1 flex-col gap-3 lg:flex-row">
              <!-- The chart -->
              <section class="h-[46vh] min-h-[20rem] rounded-card border-ui border-line bg-surface-2/40 p-3 lg:h-auto lg:min-h-0 lg:flex-1">
                <DealImpactChart
                  :dates="seriesPair.seriesWithoutTheDeal.days.map(day => day.date)"
                  :balances-before="seriesPair.seriesWithoutTheDeal.days.map(day => day.balance_dollars)"
                  :balances-after="seriesPair.seriesWithTheDeal.days.map(day => day.balance_dollars)"
                  :reserve-dollars="liquidityStore.settings.reserve_dollars"
                  :today-iso-date="todayIsoDate"
                  :deal-color-hex="dealColorHex"
                  :before-label="beforeLabel"
                  :after-label="afterLabel"
                  :lowest-after="decision.lowestAfter"
                  :back-above-reserve-date="decision.backAboveReserveAfterTheRefi?.date ?? null"
                  :refi-date="decision.refi?.date ?? null"
                  :key-dates="preview.key_dates ?? []"
                  :deal-rows-by-date="dealRowsByDate"
                />
              </section>

              <!-- The insight rail -->
              <aside data-testid="deal-import-preview.insights" aria-label="What it means" class="flex flex-col gap-3 lg:w-[24rem] lg:overflow-y-auto lg:overscroll-contain lg:pr-1">
                <!-- The crunch point -->
                <section data-insight="crunch" class="rounded-card border-ui border-line bg-surface p-4 shadow-1">
                  <h3 class="text-[10px] font-semibold uppercase tracking-[0.14em] text-fg-muted">Lowest balance</h3>
                  <div class="mt-1 flex flex-wrap items-baseline gap-x-2">
                    <span class="numeric text-2xl font-bold" :class="decision.lowestAfter.amountDollars < 0 ? 'text-negative' : decision.riskLevel === 'dips_below_reserve' ? 'text-warning' : 'text-fg'">{{ money(decision.lowestAfter.amountDollars) }}</span>
                    <span class="text-xs text-fg-muted">on {{ formatDecisionDate(decision.lowestAfter.date) }}</span>
                  </div>
                  <p class="mt-0.5 text-xs text-fg-muted">
                    {{ beforeLabel }}: <span class="numeric text-fg">{{ money(decision.lowestBefore.amountDollars) }}</span>
                    <span v-if="decision.lowestChangeDollars !== 0" class="numeric ml-1 font-semibold" :class="decision.lowestChangeDollars < 0 ? 'text-negative' : 'text-positive'">({{ formatSignedMoney(Math.round(decision.lowestChangeDollars)) }})</span>
                  </p>
                  <dl class="mt-3 space-y-1.5 border-t border-line pt-2 text-sm">
                    <div v-if="decision.cashToKeepTheReserve" data-insight="cash-to-keep-the-reserve" class="flex items-baseline justify-between gap-2">
                      <dt class="text-fg-muted">To keep your {{ money(liquidityStore.settings.reserve_dollars) }} reserve</dt>
                      <dd class="text-right"><span class="numeric font-semibold text-fg">{{ money(decision.cashToKeepTheReserve.amountDollars) }}</span><span class="block text-[10px] text-fg-muted">by {{ formatDecisionDate(decision.cashToKeepTheReserve.neededByDate) }}</span></dd>
                    </div>
                    <div v-if="decision.cashToStayAboveZero" data-insight="cash-to-stay-above-zero" class="flex items-baseline justify-between gap-2">
                      <dt class="text-fg-muted">To stay above zero</dt>
                      <dd class="text-right"><span class="numeric font-semibold text-fg">{{ money(decision.cashToStayAboveZero.amountDollars) }}</span><span class="block text-[10px] text-fg-muted">by {{ formatDecisionDate(decision.cashToStayAboveZero.neededByDate) }}</span></dd>
                    </div>
                    <div v-if="!decision.cashToKeepTheReserve" class="text-xs text-positive">
                      <dt class="sr-only">Extra cash needed</dt>
                      <dd><i class="pi pi-check mr-1 text-[10px]" aria-hidden="true"></i>No extra cash needed.</dd>
                    </div>
                  </dl>
                </section>

                <!-- Exposure and recovery -->
                <section data-insight="exposure" class="rounded-card border-ui border-line bg-surface p-4 shadow-1">
                  <h3 class="text-[10px] font-semibold uppercase tracking-[0.14em] text-fg-muted">Exposure &amp; recovery</h3>
                  <div class="mt-1 grid grid-cols-2 gap-2">
                    <div>
                      <p class="numeric text-xl font-bold" :class="decision.daysBelowReserveAfter ? 'text-warning' : 'text-fg'">{{ decision.daysBelowReserveAfter }} <span class="font-sans text-xs font-normal text-fg-muted">days</span></p>
                      <p class="text-[11px] text-fg-muted">under the reserve</p>
                    </div>
                    <div>
                      <p class="numeric text-xl font-bold" :class="decision.daysBelowZeroAfter ? 'text-negative' : 'text-fg'">{{ decision.daysBelowZeroAfter }} <span class="font-sans text-xs font-normal text-fg-muted">days</span></p>
                      <p class="text-[11px] text-fg-muted">below zero</p>
                    </div>
                  </div>
                  <ul class="mt-3 space-y-1.5 border-t border-line pt-2 text-xs">
                    <li v-if="decision.longestStretchBelowReserve" data-insight="longest-stretch" class="flex justify-between gap-2">
                      <span class="text-fg-muted">Longest stretch under the reserve</span>
                      <span class="text-right text-fg">{{ formatDecisionDate(decision.longestStretchBelowReserve.fromDate) }} → {{ decision.longestStretchBelowReserve.runsToTheEndOfTheTimeline ? 'the end' : formatDecisionDate(decision.longestStretchBelowReserve.toDate) }}</span>
                    </li>
                    <li v-if="decision.refi" data-insight="refi" class="flex justify-between gap-2">
                      <span class="text-fg-muted">Refi on {{ formatDecisionDate(decision.refi.date) }} {{ decision.refi.netDollarsOnTheDay >= 0 ? 'brings back' : 'costs' }}</span>
                      <span class="numeric text-right font-semibold" :class="decision.refi.netDollarsOnTheDay >= 0 ? 'text-positive' : 'text-negative'">{{ formatSignedMoney(Math.round(decision.refi.netDollarsOnTheDay)) }}</span>
                    </li>
                    <li data-insight="recovery" class="flex justify-between gap-2">
                      <span class="text-fg-muted">Back above the reserve</span>
                      <span v-if="decision.backAboveReserveAfterTheRefi" class="text-right text-positive">
                        {{ formatDecisionDate(decision.backAboveReserveAfterTheRefi.date) }}<template v-if="decision.backAboveReserveAfterTheRefi.daysAfterTheRefi > 0"> ({{ decision.backAboveReserveAfterTheRefi.daysAfterTheRefi }} days after the refi)</template>
                      </span>
                      <span v-else-if="decision.shortOfTheReserveAtTheEnd" class="text-right text-negative">Not in the timeline: {{ money(decision.shortOfTheReserveAtTheEnd.amountDollars) }} short on {{ formatDecisionDate(decision.shortOfTheReserveAtTheEnd.date) }}</span>
                      <span v-else class="text-right text-positive">Never under it</span>
                    </li>
                    <li v-if="decision.peakCashTiedUp" data-insight="peak-cash" class="flex justify-between gap-2">
                      <span class="text-fg-muted">Most cash tied up at once</span>
                      <span class="numeric text-right font-semibold text-fg">{{ money(decision.peakCashTiedUp.amountDollars) }} <span class="font-sans font-normal text-fg-muted">· {{ formatDecisionDate(decision.peakCashTiedUp.date) }}</span></span>
                    </li>
                  </ul>
                </section>

                <!-- The deal's cash -->
                <section data-insight="deal-cash" class="rounded-card border-ui border-line bg-surface p-4 shadow-1">
                  <h3 class="text-[10px] font-semibold uppercase tracking-[0.14em] text-fg-muted">{{ isAlreadyImported ? "The deal's cash (after the changes)" : "The deal's cash" }}</h3>
                  <div class="mt-1 grid grid-cols-3 gap-2 text-center">
                    <div><p class="numeric text-sm font-bold text-negative">−{{ money(decision.dealMoneyOutDollars) }}</p><p class="text-[10px] text-fg-muted">out</p></div>
                    <div><p class="numeric text-sm font-bold text-positive">+{{ money(decision.dealMoneyInDollars) }}</p><p class="text-[10px] text-fg-muted">in</p></div>
                    <div><p class="numeric text-sm font-bold" :class="decision.dealNetDollars < 0 ? 'text-negative' : 'text-positive'">{{ formatSignedMoney(Math.round(decision.dealNetDollars)) }}</p><p class="text-[10px] text-fg-muted">net</p></div>
                  </div>
                  <p v-if="decision.largestSingleDayOutflow" data-insight="largest-day" class="mt-2 text-xs text-fg-muted">
                    Largest single-day outflow: <span class="numeric font-semibold text-fg">{{ money(decision.largestSingleDayOutflow.amountDollars) }}</span> on {{ formatDecisionDate(decision.largestSingleDayOutflow.date) }}
                  </p>
                  <div data-insight="next-30-days" class="mt-2">
                    <div class="flex justify-between text-xs text-fg-muted">
                      <span>Cash today covers the next 30 days</span>
                      <span class="numeric font-semibold" :class="decision.next30Days.coveredFraction < 1 ? 'text-negative' : 'text-positive'">{{ Math.round(decision.next30Days.coveredFraction * 100) }}%</span>
                    </div>
                    <div class="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-3" role="progressbar" :aria-valuenow="Math.round(decision.next30Days.coveredFraction * 100)" aria-valuemin="0" aria-valuemax="100" aria-label="Cash today against the deal's money out in the next 30 days">
                      <div class="h-full rounded-full" :class="decision.next30Days.coveredFraction < 1 ? 'bg-negative' : 'bg-positive'" :style="{ width: `${Math.round(decision.next30Days.coveredFraction * 100)}%` }"></div>
                    </div>
                    <p class="mt-1 text-[10px] text-fg-muted">{{ money(decision.next30Days.cashTodayDollars) }} today vs {{ money(decision.next30Days.dealMoneyOutDollars) }} out in the next 30 days</p>
                  </div>
                </section>

                <!-- Details, on demand -->
                <section class="rounded-card border-ui border-line bg-surface shadow-1">
                  <button type="button" data-testid="deal-impact.by-month.toggle" class="flex w-full items-center justify-between px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-fg-muted hover:text-fg" :aria-expanded="byMonthOpen" @click="byMonthOpen = !byMonthOpen">
                    <span>By month</span><i class="pi text-[10px]" :class="byMonthOpen ? 'pi-chevron-up' : 'pi-chevron-down'" aria-hidden="true"></i>
                  </button>
                  <div v-if="byMonthOpen" data-testid="deal-import-preview.by-month" class="flex h-28 items-end gap-1.5 overflow-x-auto px-4 pb-3">
                    <div v-for="month in monthBars" :key="month.month" class="flex h-full min-w-[2.25rem] flex-1 flex-col items-center justify-end gap-1" :title="`${monthLabel(month.month)}: ${month.rowCount} rows, ${formatSignedMoney(Math.round(month.netDollars))}`">
                      <span class="numeric text-[9px] text-fg-muted">{{ formatSignedMoney(Math.round(month.netDollars / 1000)) }}k</span>
                      <div class="w-full rounded-t" :class="month.netDollars < 0 ? 'bg-negative/70' : 'bg-positive/70'" :style="{ height: `${month.heightPercent}%` }"></div>
                      <span class="text-[9px] text-fg-muted">{{ monthLabel(month.month) }}</span>
                    </div>
                  </div>
                </section>
                <section class="rounded-card border-ui border-line bg-surface shadow-1">
                  <button type="button" data-testid="deal-impact.rows.toggle" class="flex w-full items-center justify-between px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-fg-muted hover:text-fg" :aria-expanded="rowsOpen" @click="rowsOpen = !rowsOpen">
                    <span>{{ isAlreadyImported ? `${rowCountThatChanges} row${rowCountThatChanges === 1 ? '' : 's'} change` : `${preview.change_counts.added} rows to import` }}</span>
                    <i class="pi text-[10px]" :class="rowsOpen ? 'pi-chevron-up' : 'pi-chevron-down'" aria-hidden="true"></i>
                  </button>
                  <div v-if="rowsOpen" class="px-3 pb-3">
                    <DealCashRowChangesList
                      :changes="preview.changes"
                      :use-deal-value-for="useDealValueFor"
                      @update:use-deal-value-for="onUseDealValueForChanged"
                    />
                  </div>
                </section>
              </aside>
            </div>
          </div>
        </div>

        <!-- Phone: the actions stay at hand -->
        <div class="flex items-center gap-2 border-t border-line bg-surface/95 px-3 py-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] backdrop-blur-md sm:hidden">
          <UiButton variant="ghost" class="flex-1" @click="emit('close')">Cancel</UiButton>
          <UiButton
            data-testid="deal-import-preview.confirm-phone"
            class="flex-[2]"
            :variant="decision?.riskLevel === 'goes_negative' && !isAlreadyImported ? 'danger' : 'primary'"
            :loading="importing"
            :disabled="!preview || importing"
            @click="confirmImport"
          >{{ primaryLabel }}</UiButton>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.deal-impact-fade-enter-active,
.deal-impact-fade-leave-active {
  transition: opacity var(--dur-base) var(--ease-standard);
}
.deal-impact-fade-enter-from,
.deal-impact-fade-leave-to {
  opacity: 0;
}
.no-scrollbar {
  scrollbar-width: none;
}
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
</style>
