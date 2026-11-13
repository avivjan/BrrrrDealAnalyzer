<script setup lang="ts">
/**
 * One Bought BRRRR deal's construction account (tasks/todo/ConstructionAccountPerRehab.md): every number tied to it,
 * each with where it comes from, and every number you decide editable in place. An edit that moves the liquidity
 * timeline opens the prompt first; nothing is saved until Confirm.
 *
 * Closed, it is the two-row summary (ConstructionAccountSummaryCard); open, the detail in tabs, the Overview first
 * (tasks/todo/ConstructionAccountsCompactCardsAndRehabSummary.md). Its links reach the same deal everywhere else:
 * its modal on the Bought board, its rows on the timeline, and Mercury (Step C0).
 */
import { computed, ref, watch } from 'vue'

import { constructionAccountApi } from '../../../api/constructionAccount'
import {
  MERCURY_WEB_APP_URL, dealOnItsBoard, dealOnTheLiquidityTimeline, transactionOnTheLiquidityTimeline, type ConstructionAccountSection,
} from '../../../navigation/appLinks'
import { useConstructionAccountStore } from '../../../stores/constructionAccountStore'
import type { ConstructionAccountRehabFiguresReq, ConstructionAccountStatus, ConstructionAccountTimelineRow, ConstructionAccountTransfer } from '../../../types/constructionAccount'
import { todayISO } from '../../../utils/liquidityEngine'
import { moneyBackToYouAtTheEndDollars, rehabBudgetDifferenceOf } from '../../../utils/constructionAccountSummaryFigures'
import { mercuryAccountDisplayName } from '../../../utils/mercuryAccountDisplayName'
import { formatMoney, formatSignedMoney } from '../../../utils/money'
import type { ConstructionAccountTransferKind } from '../../../utils/constructionAccountTransferRules'
import ConstructionAccountEditableFigure from './ConstructionAccountEditableFigure.vue'
import ConstructionAccountFigure from './ConstructionAccountFigure.vue'
import ConstructionAccountManualAdjustmentsList from './ConstructionAccountManualAdjustmentsList.vue'
import ConstructionAccountSummaryCard from './ConstructionAccountSummaryCard.vue'
import ConstructionAccountTransactionsList from './ConstructionAccountTransactionsList.vue'

const props = withDefaults(defineProps<{
  status: ConstructionAccountStatus
  isHighlighted?: boolean
  /** Open: the detail shows under the summary. */
  isExpanded?: boolean
  /** A link opened the card on one of its sections. */
  openSection?: ConstructionAccountSection | null
}>(), { isHighlighted: false, isExpanded: false, openSection: null })

const emit = defineEmits<{
  (e: 'link', status: ConstructionAccountStatus): void
  (e: 'switchAccount', status: ConstructionAccountStatus): void
  /** Deposit, Steal or Close out: the page opens the transfer window. */
  (e: 'transfer', status: ConstructionAccountStatus, kind: ConstructionAccountTransferKind): void
  /** Open or close the detail. */
  (e: 'toggle', status: ConstructionAccountStatus): void
}>()

const store = useConstructionAccountStore()
const errorMessage = ref<string | null>(null)
const savingFigure = ref<string | null>(null)

type ConstructionAccountDetailTab = 'overview' | 'money-flow' | 'transactions' | 'manual-entries' | 'timeline' | 'account'
const DETAIL_TAB_LABELS: Record<ConstructionAccountDetailTab, string> = {
  overview: 'Overview', 'money-flow': 'Draws & payments', transactions: 'Bank transactions', 'manual-entries': 'Entered by hand',
  timeline: 'Timeline & transfers', account: 'Account',
}
const activeDetailTab = ref<ConstructionAccountDetailTab>('overview')
watch(() => props.openSection, (section) => {
  if (section === 'manual-entries') activeDetailTab.value = 'manual-entries'
  if (section === 'transactions') activeDetailTab.value = 'transactions'
}, { immediate: true })

const id = computed(() => props.status.bought_deal_id)
const hook = (name: string) => `ca.${id.value}.${name}`
const detailElementId = computed(() => `construction-account-detail-${id.value}`)
const isLive = computed(() => props.status.is_linked && !props.status.closed_out_at)
const rehabIsOverBudget = computed(() => props.status.original_steal_dollars < 0)
const rehabBudgetDifference = computed(() => rehabBudgetDifferenceOf(props.status))
const moneyBackToYouAtTheEnd = computed(() => moneyBackToYouAtTheEndDollars(props.status))
/** "Deposit due" on a live account is the Deposit button right below: no second call to action. */
const attentionReasonsWithoutAButtonBelow = computed(() =>
  props.status.needs_attention_because.filter(reason => !(reason === 'deposit_due' && isLive.value)))
const visibleDetailTabs = computed<ConstructionAccountDetailTab[]>(() => props.status.is_linked
  ? ['overview', 'money-flow', 'transactions', 'manual-entries', 'timeline', 'account']
  : ['overview', 'timeline'])

const ATTENTION_LABELS = { deposit_due: 'Deposit due', top_up_needed: 'Top-up needed', mercury_unavailable: 'Mercury unavailable' } as const
const CAP_LABELS = {
  available_balance: 'Limited by what is in the account right now',
  buffer_to_keep: 'Limited by the buffer you keep in the account',
  projected_return: 'Limited by what the account will give back at the end',
} as const
const ROW_LABELS: Record<string, string> = {
  construction_account_deposit: 'Your deposit', construction_account_balance_returned_at_rehab_end: 'Back to you at rehab end',
  construction_account_top_up_needed: 'Top-up needed', appliances: 'Appliances',
}

const TRANSFER_OUTCOME_LABELS = {
  being_sent: 'Being sent', accepted_by_mercury: 'Accepted', waiting_for_approval_in_mercury: 'Approve it in Mercury',
  refused_by_mercury: 'Refused', mercury_did_not_answer: 'No answer: check Mercury',
  failed_or_cancelled_at_mercury: 'Failed or cancelled',
} as const
/** What Mercury said about an approval request: rejected or cancelled there, or approved and not sent yet. */
function transferOutcomeLabel(transfer: ConstructionAccountTransfer): string {
  if (transfer.transfer_outcome === 'failed_or_cancelled_at_mercury' && transfer.mercury_transfer_status === 'rejected') return 'Rejected in Mercury'
  if (transfer.transfer_outcome === 'failed_or_cancelled_at_mercury' && transfer.mercury_transfer_status === 'cancelled') return 'Cancelled in Mercury'
  if (transfer.transfer_outcome === 'waiting_for_approval_in_mercury' && transfer.mercury_transfer_status === 'approved') return 'Approved, waiting for Mercury to send it'
  return TRANSFER_OUTCOME_LABELS[transfer.transfer_outcome]
}
const TRANSFER_OUTCOME_TONES = {
  being_sent: 'neutral', accepted_by_mercury: 'positive', waiting_for_approval_in_mercury: 'warning', refused_by_mercury: 'negative',
  mercury_did_not_answer: 'warning',
  failed_or_cancelled_at_mercury: 'negative',
} as const

function timelineRowOf(itemKey: string): ConstructionAccountTimelineRow | undefined {
  return props.status.timeline_rows.find(row => row.item_key === itemKey && !row.is_done)
    ?? props.status.timeline_rows.find(row => row.item_key === itemKey)
}

function attentionLink(reason: keyof typeof ATTENTION_LABELS) {
  const row = reason === 'deposit_due' ? timelineRowOf('construction_account_deposit')
    : reason === 'top_up_needed' ? timelineRowOf('construction_account_top_up_needed') : undefined
  return row ? transactionOnTheLiquidityTimeline(row.transaction_id, row.effective_date) : undefined
}

function errorMessageOf(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : 'That could not be saved. Nothing was changed.'
}

async function run(figure: string, action: () => Promise<unknown>) {
  errorMessage.value = null
  savingFigure.value = figure
  try {
    await action()
  } catch (error) {
    errorMessage.value = errorMessageOf(error)
  } finally {
    savingFigure.value = null
  }
}

const saveRehabFigure = (figure: string, data: ConstructionAccountRehabFiguresReq, title: string) =>
  run(figure, () => store.saveRehabFigures(id.value, data, title))

/** The baselines and the buffer are part of the link: send it whole, with the one value changed. */
function saveLinkFigure(figure: string, changes: Partial<Record<'loan_draws_pulled_before_construction_account_dollars'
  | 'rehab_payments_made_before_construction_account_dollars' | 'minimum_balance_to_keep_in_construction_account_dollars', number>>, title: string) {
  const status = props.status
  if (!status.construction_account || !status.primary_checking_account) return
  return run(figure, () => store.saveLink(id.value, {
    construction_mercury_account_id: status.construction_account!.mercury_account_id,
    primary_checking_mercury_account_id: status.primary_checking_account!.mercury_account_id,
    loan_draws_pulled_before_construction_account_dollars: status.loan_draws_pulled_before_construction_account_dollars ?? 0,
    rehab_payments_made_before_construction_account_dollars: status.rehab_payments_made_before_construction_account_dollars ?? 0,
    minimum_balance_to_keep_in_construction_account_dollars: status.minimum_balance_to_keep_in_construction_account_dollars ?? 0,
    ...changes,
  }, title))
}

const unlink = () => run('unlink', () => store.unlink(id.value))
const markReadyForCloseOut = () => run('ready', () => store.markReadyForCloseOut(id.value))
const markClosedOut = () => run('closed-out', () => store.markClosedOut(id.value))
const reopen = () => run('reopen', () => store.reopen(id.value))
const refreshFromMercury = () => run('refresh', async () => {
  await constructionAccountApi.refresh(todayISO())
  await store.load()
})

function sourceLine(sum: ConstructionAccountStatus['loan_draws_pulled']): string {
  if (!sum) return ''
  return `From the bank ${formatMoney(sum.from_the_bank_feed_dollars)} + before this account ${formatMoney(sum.before_this_account_dollars)} `
    + `+ entered by hand ${formatMoney(sum.entered_by_hand_dollars)}`
}

function percent(value: number | null): string {
  return value == null ? '—' : `${value}%`
}

function shortDateTime(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : 'never'
}
</script>

<template>
  <UiSurface
    :data-testid="`ca.${status.bought_deal_id}`"
    :id="`construction-account-${status.bought_deal_id}`"
    :level="1"
    padding="md"
    class="scroll-mt-24"
    :class="isHighlighted ? 'ring-2 ring-primary' : ''"
    :data-highlighted="isHighlighted ? 'true' : undefined"
    :data-expanded="isExpanded ? 'true' : 'false'"
  >
    <ConstructionAccountSummaryCard :status="status" :is-expanded="isExpanded" :detail-element-id="detailElementId"
                                    @toggle="emit('toggle', status)" @link="emit('link', status)" />

    <div v-if="isExpanded" :id="detailElementId" :data-testid="hook('detail')" class="mt-4 space-y-4 border-t border-line pt-4">
      <!-- Where the money is, and the links to the same deal elsewhere -->
      <div class="flex flex-wrap items-center justify-between gap-2">
        <p :data-testid="hook('accounts')" class="min-w-0 text-xs text-fg-muted">
          <template v-if="status.construction_account">
            <span class="text-fg">{{ mercuryAccountDisplayName(status.construction_account) }}</span>
            <span aria-hidden="true"> ⇄ </span><span class="sr-only"> paired with </span>
            <span class="text-fg">{{ mercuryAccountDisplayName(status.primary_checking_account) }}</span>
            <template v-if="status.mercury_workspace_label"> · LLC {{ status.mercury_workspace_label }}</template>
          </template>
          <template v-else>No construction account linked yet. The numbers below are the plan from the deal.</template>
        </p>
        <div class="flex flex-wrap items-center gap-1">
          <RouterLink :data-testid="hook('open-deal')" :to="dealOnItsBoard('bought', status.bought_deal_id)"
                      class="inline-flex items-center gap-1 rounded-ctl px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10">
            <i class="pi pi-external-link text-[10px]" aria-hidden="true"></i>Open deal
          </RouterLink>
          <RouterLink v-if="status.is_in_the_liquidity_timeline" :data-testid="hook('show-on-timeline')" :to="dealOnTheLiquidityTimeline('bought', status.bought_deal_id)"
                      class="inline-flex items-center gap-1 rounded-ctl px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10">
            <i class="pi pi-chart-line text-[10px]" aria-hidden="true"></i>On the timeline
          </RouterLink>
          <a v-if="status.is_linked" :data-testid="hook('open-mercury')" :href="MERCURY_WEB_APP_URL" target="_blank" rel="noopener noreferrer"
             class="inline-flex items-center gap-1 rounded-ctl px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10">
            <i class="pi pi-building-columns text-[10px]" aria-hidden="true"></i>Open Mercury
          </a>
        </div>
      </div>

      <div v-if="attentionReasonsWithoutAButtonBelow.length" :data-testid="hook('attention')" class="flex flex-wrap gap-2">
        <template v-for="reason in attentionReasonsWithoutAButtonBelow" :key="reason">
          <button v-if="reason === 'deposit_due' && isLive" type="button" :data-testid="hook(`attention.${reason}`)" @click="emit('transfer', status, 'deposit')"
                  class="inline-flex items-center gap-1.5 rounded-full border border-warning/40 bg-warning/10 px-3 py-1 text-xs font-medium text-warning hover:bg-warning/20">
            <i class="pi pi-exclamation-triangle text-[10px]" aria-hidden="true"></i>{{ ATTENTION_LABELS[reason] }}: deposit now
          </button>
          <RouterLink v-else-if="attentionLink(reason)" :data-testid="hook(`attention.${reason}`)" :to="attentionLink(reason)!"
                      class="inline-flex items-center gap-1.5 rounded-full border border-warning/40 bg-warning/10 px-3 py-1 text-xs font-medium text-warning hover:bg-warning/20">
            <i class="pi pi-exclamation-triangle text-[10px]" aria-hidden="true"></i>{{ ATTENTION_LABELS[reason] }}: see it on the timeline
          </RouterLink>
          <button v-else type="button" :data-testid="hook(`attention.${reason}`)" @click="refreshFromMercury"
                  class="inline-flex items-center gap-1.5 rounded-full border border-warning/40 bg-warning/10 px-3 py-1 text-xs font-medium text-warning hover:bg-warning/20">
            <i class="pi pi-exclamation-triangle text-[10px]" aria-hidden="true"></i>{{ ATTENTION_LABELS[reason] }}: try again
          </button>
        </template>
      </div>

      <p v-if="errorMessage" :data-testid="hook('error')" role="alert" class="rounded-ctl border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">{{ errorMessage }}</p>

      <!-- Move money: the app asks Mercury (each one asks for your passkey) -->
      <div v-if="isLive" :data-testid="hook('transfer-actions')" class="flex flex-wrap items-center gap-2">
        <UiButton size="sm" :data-testid="hook('deposit')" @click="emit('transfer', status, 'deposit')">
          <i class="pi pi-arrow-down mr-1.5 text-xs" aria-hidden="true"></i>Deposit
        </UiButton>
        <UiButton size="sm" variant="secondary" :data-testid="hook('steal')" @click="emit('transfer', status, 'steal')">
          <i class="pi pi-arrow-up mr-1.5 text-xs" aria-hidden="true"></i>Steal
        </UiButton>
        <UiButton size="sm" variant="secondary" :data-testid="hook('close-out')" @click="emit('transfer', status, 'close_out')">Close out</UiButton>
        <span class="text-xs text-fg-muted">Deposit moves money from checking into this account; Steal takes money out to checking.</span>
      </div>

      <!-- The detail, one subject per tab -->
      <UiTabs :aria-label="`${status.deal_address}: details`" class="max-w-full">
        <UiButton v-for="tab in visibleDetailTabs" :key="tab" :data-testid="hook(`tab.${tab}`)"
                  variant="tab" size="sm" :active="activeDetailTab === tab" class="min-h-9 shrink-0 touch:min-h-11 px-3" @click="activeDetailTab = tab">
          {{ DETAIL_TAB_LABELS[tab] }}
          <span v-if="tab === 'manual-entries' && status.manual_adjustments.length" class="ml-1 text-xs text-fg-muted">{{ status.manual_adjustments.length }}</span>
        </UiButton>
      </UiTabs>

      <!-- Overview: the plan, your money, and the outcome -->
      <div v-if="activeDetailTab === 'overview'" :data-testid="hook('panel.overview')" role="tabpanel" class="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <section :data-testid="hook('rehab')" aria-label="The rehab plan" class="space-y-2 rounded-ctl border border-line p-3">
          <h3 class="text-xs font-medium uppercase tracking-[0.12em] text-fg-muted">The rehab plan</h3>
          <ConstructionAccountEditableFigure :testid="hook('actual-rehab-cost')" label="Actual rehab cost" :value="status.actual_rehab_cost_dollars"
            :is-saving="savingFigure === 'actual-rehab-cost'" explanation="Before the contingency. Saved on the Bought deal too."
            @save="value => saveRehabFigure('actual-rehab-cost', { actual_rehab_cost_dollars: value }, 'Change the actual rehab cost')" />
          <ConstructionAccountEditableFigure :testid="hook('contingency')" label="Contingency" unit="percent" :value="status.rehab_contingency_percent"
            :is-saving="savingFigure === 'contingency'"
            @save="value => saveRehabFigure('contingency', { rehab_contingency_percent: value }, 'Change the rehab contingency')" />
          <ConstructionAccountFigure :testid="hook('rehab-cost')" label="Rehab cost" :value="status.rehab_cost_dollars" emphasis
            explanation="Actual rehab cost + contingency. Appliances are paid from checking, not from here." />
          <ConstructionAccountEditableFigure :testid="hook('construction-budget')" label="Lender's construction budget" :value="status.construction_budget_dollars"
            :is-saving="savingFigure === 'construction-budget'" explanation="The most the lender will pay out in draws"
            @save="value => saveRehabFigure('construction-budget', { construction_budget_dollars: value }, 'Change the construction budget')" />
          <ConstructionAccountFigure :testid="hook('original-steal')" emphasis
            :label="rehabBudgetDifference.kind === 'over_budget_you_cover' ? 'Over budget: you cover' : 'Under budget: you keep'"
            :value="rehabBudgetDifference.dollars" :tone="rehabIsOverBudget ? 'warning' : 'positive'"
            :explanation="rehabIsOverBudget ? 'The rehab costs more than the lender pays: you add the difference.' : 'The lender pays more than the rehab costs: the difference is yours.'" />
        </section>

        <section :data-testid="hook('own-money')" aria-label="Your money" class="space-y-2 rounded-ctl border border-line p-3">
          <h3 class="text-xs font-medium uppercase tracking-[0.12em] text-fg-muted">Your money</h3>
          <ConstructionAccountEditableFigure :testid="hook('cushion')" label="Your deposit (cushion)" :value="status.rehab_cushion_dollars"
            :is-saving="savingFigure === 'cushion'" :explanation="`Suggested ${formatMoney(status.suggested_rehab_cushion_dollars)}. Saved on the Bought deal too.`"
            @save="value => saveRehabFigure('cushion', { rehab_cushion_dollars: value }, 'Change the rehab cushion')" />
          <div v-if="status.rehab_cushion_dollars !== status.suggested_rehab_cushion_dollars" class="flex justify-end">
            <UiButton variant="ghost" size="sm" :data-testid="hook('cushion.reset')"
                      @click="saveRehabFigure('cushion', { rehab_cushion_dollars: status.suggested_rehab_cushion_dollars }, 'Reset the rehab cushion to the suggested amount')">
              Reset to suggested ({{ formatMoney(status.suggested_rehab_cushion_dollars) }})
            </UiButton>
          </div>
          <ConstructionAccountFigure :testid="hook('total-to-deposit')" label="You deposit in all" :value="status.total_to_deposit_dollars" emphasis
            :explanation="rehabIsOverBudget ? `Cushion ${formatMoney(status.rehab_cushion_dollars)} + the rehab beyond the budget ${formatMoney(status.rehab_beyond_the_construction_budget_dollars)}` : 'The cushion'" />
          <template v-if="status.is_linked">
            <ConstructionAccountFigure :testid="hook('deposited')" label="Deposited so far" :value="status.own_money_transferred_into_the_account_dollars" />
            <ConstructionAccountFigure :testid="hook('remaining-deposit')" label="Still to deposit" :value="status.remaining_deposit_dollars"
              :tone="(status.remaining_deposit_dollars ?? 0) > 0 ? 'warning' : 'neutral'" />
            <ConstructionAccountFigure :testid="hook('stolen')" label="Taken out so far (steals)" :value="status.own_money_transferred_out_of_the_account_dollars" />
            <ConstructionAccountFigure :testid="hook('own-money-inside')" label="Your money still in the account" :value="status.own_money_still_in_the_account_dollars"
              explanation="Deposited − taken out" />
            <ConstructionAccountFigure v-if="(status.spread_already_taken_dollars ?? 0) > 0" :testid="hook('spread-taken')" label="Budget spread already taken" :value="status.spread_already_taken_dollars" />
            <ConstructionAccountEditableFigure :testid="hook('buffer')" label="Always keep in the account" :value="status.minimum_balance_to_keep_in_construction_account_dollars ?? 0"
              :is-saving="savingFigure === 'buffer'" explanation="A buffer for bills the lender reimburses later. Lowers what is safe to take out."
              @save="value => saveLinkFigure('buffer', { minimum_balance_to_keep_in_construction_account_dollars: value }, 'Change the buffer to keep')" />
          </template>
        </section>

        <section :data-testid="hook('outcome')" aria-label="Now and at the end" class="space-y-2 rounded-ctl border border-line p-3">
          <h3 class="text-xs font-medium uppercase tracking-[0.12em] text-fg-muted">{{ status.is_linked ? 'Now and at the end' : 'At the end' }}</h3>
          <template v-if="status.is_linked">
            <ConstructionAccountFigure :testid="hook('balance')" label="In the account now" :value="status.current_balance_dollars" emphasis
              :explanation="`Available ${formatMoney(status.available_balance_dollars)}`" />
            <ConstructionAccountFigure v-if="status.pending_money_in_dollars" :testid="hook('pending-in')" label="On the way in" :value="status.pending_money_in_dollars" explanation="Accepted by the bank, not settled yet" />
            <ConstructionAccountFigure v-if="status.pending_money_out_dollars" :testid="hook('pending-out')" label="On the way out" :value="status.pending_money_out_dollars" explanation="Sent, not settled yet" />
          </template>
          <ConstructionAccountFigure :testid="hook('projected-return')" :label="status.closed_out_at ? 'Came back to you' : 'Back to you when the rehab ends'" :value="moneyBackToYouAtTheEnd" emphasis
            tone="positive"
            :explanation="status.is_linked
              ? `In the account + the draws still to come − the rehab still to pay${(status.remaining_deposit_dollars ?? 0) > 0 ? ' + the deposit you still owe' : ''}`
              : 'Your deposit + what you keep under budget'" />
          <template v-if="status.is_linked">
            <ConstructionAccountFigure :testid="hook('own-money-back')" label="· of it, your own money" :value="(status.own_money_back_at_rehab_end_dollars ?? 0) + (status.remaining_deposit_dollars ?? 0)" />
            <ConstructionAccountFigure :testid="hook('spread-back')" label="· of it, the budget spread" :value="status.spread_at_rehab_end_dollars" />
            <ConstructionAccountFigure :testid="hook('safe-to-steal')" label="Safe to take out now (steal)" :value="status.safe_to_steal_now_dollars" emphasis
              :explanation="status.safe_to_steal_now_is_capped_by ? CAP_LABELS[status.safe_to_steal_now_is_capped_by] : undefined" />
            <ConstructionAccountFigure v-if="(status.top_up_needed_dollars ?? 0) > 0" :testid="hook('top-up')" label="You need to add now" :value="status.top_up_needed_dollars"
              tone="negative" explanation="The account can't pay the rest of the rehab without it" />
            <ConstructionAccountFigure :testid="hook('checking-available')" label="Available in checking" :value="status.primary_checking_available_balance_dollars"
              explanation="Where a deposit comes from and a steal goes to" />
            <div class="flex flex-wrap items-center justify-between gap-2 pt-1 text-xs text-fg-muted">
              <span :data-testid="hook('as-of')">Bank amounts as of {{ shortDateTime(status.amounts_as_of) }}</span>
              <UiButton variant="ghost" size="sm" :data-testid="hook('refresh')" :loading="savingFigure === 'refresh'" @click="refreshFromMercury">Refresh</UiButton>
            </div>
          </template>
        </section>
      </div>

      <!-- Draws & payments: each total by where it comes from -->
      <div v-else-if="activeDetailTab === 'money-flow'" :data-testid="hook('panel.money-flow')" role="tabpanel" class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <section :data-testid="hook('draws')" aria-label="Lender draws" class="space-y-2 rounded-ctl border border-line p-3">
          <h3 class="text-xs font-medium uppercase tracking-[0.12em] text-fg-muted">Lender draws · {{ percent(status.percent_of_the_construction_budget_pulled) }} of the budget</h3>
          <ConstructionAccountFigure :testid="hook('draws-pulled')" label="Received so far" :value="status.loan_draws_pulled?.total_dollars" emphasis :explanation="sourceLine(status.loan_draws_pulled)" />
          <ConstructionAccountFigure :testid="hook('draws-remaining')" label="Still to come from the lender" :value="status.loan_draws_remaining_to_pull_dollars" />
          <ConstructionAccountFigure :testid="hook('draw-count')" label="Number of draws" :value="status.loan_draw_count != null ? String(status.loan_draw_count) : null" />
          <ConstructionAccountFigure :testid="hook('last-draw')" label="Last draw"
            :value="status.last_loan_draw ? `${formatMoney(status.last_loan_draw.amount_dollars)} on ${status.last_loan_draw.date}` : null" />
          <ConstructionAccountEditableFigure :testid="hook('draws-before')" label="Draws received before this account existed" :value="status.loan_draws_pulled_before_construction_account_dollars ?? 0"
            :is-saving="savingFigure === 'draws-before'" explanation="Draws that landed somewhere else first"
            @save="value => saveLinkFigure('draws-before', { loan_draws_pulled_before_construction_account_dollars: value }, 'Change the draws pulled before this account')" />
        </section>
        <section :data-testid="hook('paid')" aria-label="Paid to contractors" class="space-y-2 rounded-ctl border border-line p-3">
          <h3 class="text-xs font-medium uppercase tracking-[0.12em] text-fg-muted">Paid to contractors · {{ percent(status.percent_of_the_rehab_paid) }} of the rehab</h3>
          <ConstructionAccountFigure :testid="hook('paid-until-now')" label="Paid so far" :value="status.rehab_payments_made?.total_dollars" emphasis :explanation="sourceLine(status.rehab_payments_made)" />
          <ConstructionAccountFigure :testid="hook('unpaid')" label="Still to pay" :value="status.unpaid_rehab_remaining_dollars" />
          <ConstructionAccountFigure :testid="hook('last-payment')" label="Last payment"
            :value="status.last_rehab_payment ? `${formatMoney(status.last_rehab_payment.amount_dollars)} to ${status.last_rehab_payment.counterparty_name} on ${status.last_rehab_payment.date}` : null" />
          <ConstructionAccountEditableFigure :testid="hook('paid-before')" label="Paid before this account existed" :value="status.rehab_payments_made_before_construction_account_dollars ?? 0"
            :is-saving="savingFigure === 'paid-before'" explanation="Rehab paid from somewhere else first"
            @save="value => saveLinkFigure('paid-before', { rehab_payments_made_before_construction_account_dollars: value }, 'Change the rehab paid before this account')" />
          <div v-if="status.rehab_paid_by_payee.length">
            <p class="mb-1 text-xs text-fg-muted">Paid to each contractor</p>
            <ul :data-testid="hook('paid-by-payee')" class="divide-y divide-line rounded-ctl border border-line">
              <li v-for="payee in status.rehab_paid_by_payee" :key="payee.payee_name" class="flex justify-between gap-3 px-3 py-1.5 text-sm">
                <span class="min-w-0 truncate text-fg">{{ payee.payee_name }}</span><span class="numeric">{{ formatMoney(payee.amount_dollars) }}</span>
              </li>
            </ul>
          </div>
        </section>
      </div>

      <!-- The bank feed, with its own corrections -->
      <div v-else-if="activeDetailTab === 'transactions'" :data-testid="hook('transactions-section')" role="tabpanel" class="space-y-2">
        <p class="text-xs text-fg-muted">
          {{ status.transactions_counted_count ?? 0 }} counted · {{ status.transactions_ignored_count ?? 0 }} ignored ·
          {{ status.transactions_recategorised_count ?? 0 }} re-categorised · {{ status.transactions_failed_or_cancelled_count ?? 0 }} failed ·
          last one {{ status.last_transaction_date ?? 'none yet' }}
        </p>
        <ConstructionAccountTransactionsList :bought-deal-id="status.bought_deal_id" @error="message => (errorMessage = message)" />
      </div>

      <!-- Money that never touched this account -->
      <div v-else-if="activeDetailTab === 'manual-entries'" :data-testid="hook('manual-entries-section')" role="tabpanel" class="space-y-2">
        <p class="text-xs text-fg-muted">Payments and draws that never went through this account: a contractor paid from another account, a card, cash, or a draw wired elsewhere.</p>
        <ConstructionAccountManualAdjustmentsList :bought-deal-id="status.bought_deal_id" :adjustments="status.manual_adjustments" @error="message => (errorMessage = message)" />
      </div>

      <!-- On the timeline, and the transfers made here -->
      <div v-else-if="activeDetailTab === 'timeline'" role="tabpanel" class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <section :data-testid="hook('timeline-rows')" aria-label="On the liquidity timeline" class="space-y-1 rounded-ctl border border-line p-3">
          <h3 class="text-xs font-medium uppercase tracking-[0.12em] text-fg-muted">On the liquidity timeline</h3>
          <p v-if="!status.is_in_the_liquidity_timeline" class="text-xs text-fg-muted">This deal is not in the liquidity timeline yet: import it from the deal's modal.</p>
          <RouterLink v-for="row in status.timeline_rows" :key="row.transaction_id" :data-testid="hook(`timeline-row.${row.item_key}`)"
                      :to="transactionOnTheLiquidityTimeline(row.transaction_id, row.effective_date)"
                      class="flex flex-wrap items-center justify-between gap-2 rounded-ctl px-2 py-1.5 text-sm hover:bg-surface-3">
            <span class="text-fg">
              {{ ROW_LABELS[row.item_key] ?? row.description }}
              <span class="ml-1 text-xs text-fg-muted">{{ row.effective_date }}</span>
              <UiBadge v-if="row.is_done" tone="neutral" class="ml-1">Done</UiBadge>
              <UiBadge v-else-if="row.is_overdue" tone="warning" class="ml-1">Overdue</UiBadge>
              <span v-if="row.item_key === 'appliances'" class="ml-1 text-xs text-fg-muted">· paid from checking, not this account</span>
            </span>
            <span class="numeric font-semibold">{{ formatSignedMoney(row.amount_dollars) }}</span>
          </RouterLink>
          <p class="pt-1 text-xs text-fg-muted">
            Rehab done {{ status.rehab_completed_date }}{{ status.rehab_completed_is_approved ? ' (approved)' : '' }} ·
            refi {{ status.refi_closing_date }}{{ status.refi_closed_is_approved ? ' (approved)' : '' }}. Change these dates from the deal on the timeline.
          </p>
        </section>
        <section v-if="status.is_linked" :data-testid="hook('transfers')" aria-label="Transfers made in the app" class="space-y-2 rounded-ctl border border-line p-3 text-sm">
          <h3 class="text-xs font-medium uppercase tracking-[0.12em] text-fg-muted">Transfers made in the app · {{ status.transfers_made_in_the_app.length }}</h3>
          <p :data-testid="hook('transfer-limits')" class="text-xs text-fg-muted">
            {{ status.transfers_left_this_hour ?? '—' }} left this hour · at most {{ formatMoney(status.maximum_single_transfer_dollars) }} each ·
            <template v-if="!status.in_app_transfers_are_enabled">turned off in the settings · </template>
            <template v-if="status.has_a_transfer_token">transfer token found</template>
            <template v-else>no transfer token: add <code class="font-mono">{{ status.transfer_token_environment_variable_name }}</code> to the hosting secrets</template>
          </p>
          <p v-if="!status.transfers_made_in_the_app.length" class="text-xs text-fg-muted">None yet. Transfers you make in Mercury itself show in the bank transactions.</p>
          <ul v-else class="divide-y divide-line">
            <li v-for="transfer in status.transfers_made_in_the_app" :key="transfer.transfer_id" :data-testid="hook(`transfer.${transfer.transfer_id}`)"
                class="flex flex-wrap items-center justify-between gap-2 py-1.5">
              <span>
                {{ transfer.transfer_direction === 'deposit_into_construction_account' ? 'Deposit' : 'Steal' }}
                <span class="ml-1 text-xs text-fg-muted">{{ shortDateTime(transfer.requested_at) }}</span>
                <UiBadge :tone="TRANSFER_OUTCOME_TONES[transfer.transfer_outcome]" class="ml-1">{{ transferOutcomeLabel(transfer) }}<template v-if="transfer.mercury_refusal_http_status"> ({{ transfer.mercury_refusal_http_status }})</template></UiBadge>
                <span v-if="transfer.transfer_outcome === 'accepted_by_mercury'" class="ml-1 text-xs text-fg-muted">
                  {{ transfer.is_in_the_bank_feed ? 'in the bank feed' : 'not in the bank feed yet' }}
                </span>
              </span>
              <span class="numeric font-semibold">{{ formatMoney(transfer.amount_dollars) }}</span>
            </li>
          </ul>
        </section>
      </div>

      <!-- The account itself: its settings, its history, closing it -->
      <div v-else-if="activeDetailTab === 'account'" :data-testid="hook('panel.account')" role="tabpanel" class="space-y-3">
        <p :data-testid="hook('history')" class="text-xs text-fg-muted">
          Linked {{ status.construction_account ? mercuryAccountDisplayName(status.construction_account) : '' }}
          <template v-if="status.previous_construction_mercury_account_ids.length"> · earlier accounts: {{ status.previous_construction_mercury_account_ids.length }}</template>
          <template v-if="status.marked_ready_for_close_out_at"> · ready for close-out</template>
          <template v-if="status.closed_out_at"> · closed out {{ shortDateTime(status.closed_out_at) }}</template>
        </p>
        <div class="flex flex-wrap gap-2">
          <UiButton variant="secondary" size="sm" :data-testid="hook('edit-link')" @click="emit('link', status)">Account settings</UiButton>
          <UiButton v-if="isLive" variant="ghost" size="sm" :data-testid="hook('switch')" @click="emit('switchAccount', status)">Switch account</UiButton>
          <UiButton v-if="isLive && !status.marked_ready_for_close_out_at" variant="ghost" size="sm" :data-testid="hook('mark-ready')" @click="markReadyForCloseOut">Mark ready for close-out</UiButton>
          <UiButton v-if="isLive" variant="secondary" size="sm" :data-testid="hook('mark-closed-out')" @click="markClosedOut">Mark closed out (no transfer)</UiButton>
          <UiButton v-if="status.closed_out_at" variant="secondary" size="sm" :data-testid="hook('reopen')" @click="reopen">Reopen</UiButton>
          <UiButton variant="danger" size="sm" :data-testid="hook('unlink')" @click="unlink">Unlink</UiButton>
        </div>
      </div>
    </div>
  </UiSurface>
</template>
