<script setup lang="ts">
/**
 * One Bought BRRRR deal's construction account (tasks/todo/ConstructionAccountPerRehab.md): every number tied to it,
 * each with where it comes from, and every number you decide editable in place. An edit that moves the liquidity
 * timeline opens the prompt first; nothing is saved until Confirm.
 *
 * Opens on the outcome and the account now; the other groups expand. Its links reach the same deal everywhere else:
 * its modal on the Bought board, its rows on the timeline, and Mercury (Step C0).
 */
import { constructionAccountStateOf } from '../../../utils/constructionAccountState'
import { computed, ref, watch } from 'vue'

import { constructionAccountApi } from '../../../api/constructionAccount'
import {
  MERCURY_WEB_APP_URL, dealOnItsBoard, dealOnTheLiquidityTimeline, transactionOnTheLiquidityTimeline, type ConstructionAccountSection,
} from '../../../navigation/appLinks'
import { useConstructionAccountStore } from '../../../stores/constructionAccountStore'
import type { ConstructionAccountRehabFiguresReq, ConstructionAccountStatus, ConstructionAccountTimelineRow } from '../../../types/constructionAccount'
import { todayISO } from '../../../utils/liquidityEngine'
import { formatMoney, formatSignedMoney } from '../../../utils/money'
import type { ConstructionAccountTransferKind } from '../../../utils/constructionAccountTransferRules'
import ConstructionAccountEditableFigure from './ConstructionAccountEditableFigure.vue'
import ConstructionAccountFigure from './ConstructionAccountFigure.vue'
import ConstructionAccountManualAdjustmentsList from './ConstructionAccountManualAdjustmentsList.vue'
import ConstructionAccountTransactionsList from './ConstructionAccountTransactionsList.vue'

const props = withDefaults(defineProps<{
  status: ConstructionAccountStatus
  isHighlighted?: boolean
  /** A link opened the card on one of its sections. */
  openSection?: ConstructionAccountSection | null
}>(), { isHighlighted: false, openSection: null })

const emit = defineEmits<{
  (e: 'link', status: ConstructionAccountStatus): void
  (e: 'switchAccount', status: ConstructionAccountStatus): void
  /** Deposit, Steal or Close out: the page opens the transfer window. */
  (e: 'transfer', status: ConstructionAccountStatus, kind: ConstructionAccountTransferKind): void
}>()

const store = useConstructionAccountStore()
const errorMessage = ref<string | null>(null)
const savingFigure = ref<string | null>(null)
const manualEntriesOpen = ref(false)
const transactionsOpen = ref(false)
watch(() => props.openSection, (section) => {
  if (section === 'manual-entries') manualEntriesOpen.value = true
  if (section === 'transactions') transactionsOpen.value = true
}, { immediate: true })

const id = computed(() => props.status.bought_deal_id)
const hook = (name: string) => `ca.${id.value}.${name}`
const isLive = computed(() => props.status.is_linked && !props.status.closed_out_at)
const rehabIsOverBudget = computed(() => props.status.original_steal_dollars < 0)

const ATTENTION_LABELS = { deposit_due: 'Deposit due', top_up_needed: 'Top-up needed', mercury_unavailable: 'Mercury unavailable' } as const
const CAP_LABELS = {
  available_balance: 'capped by what is in the account',
  buffer_to_keep: 'capped by the buffer you keep in the account',
  projected_return: 'capped by what the account will give back',
} as const
const ROW_LABELS: Record<string, string> = {
  construction_account_deposit: 'Deposit', construction_account_balance_returned_at_rehab_end: 'Return at rehab end',
  construction_account_top_up_needed: 'Top-up needed', appliances: 'Appliances',
}

const stateChip = computed(() => constructionAccountStateOf(props.status))
const TRANSFER_OUTCOME_LABELS = {
  being_sent: 'Being sent', accepted_by_mercury: 'Accepted', refused_by_mercury: 'Refused', mercury_did_not_answer: 'No answer: check Mercury',
  failed_or_cancelled_at_mercury: 'Failed or cancelled',
} as const
const TRANSFER_OUTCOME_TONES = {
  being_sent: 'neutral', accepted_by_mercury: 'positive', refused_by_mercury: 'negative', mercury_did_not_answer: 'warning',
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
  return `bank feed ${formatMoney(sum.from_the_bank_feed_dollars)} + before this account ${formatMoney(sum.before_this_account_dollars)} `
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
    class="scroll-mt-24 space-y-4"
    :class="isHighlighted ? 'ring-2 ring-primary' : ''"
    :data-highlighted="isHighlighted ? 'true' : undefined"
  >
    <!-- Header: the deal, its state, its links -->
    <header class="flex flex-wrap items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 :data-testid="hook('address')" class="truncate font-display text-lg font-semibold tracking-display text-fg">{{ status.deal_address }}</h2>
        <p class="mt-0.5 text-xs text-fg-muted">
          <template v-if="status.mercury_workspace_label">LLC {{ status.mercury_workspace_label }} · </template>
          <template v-if="status.construction_account">
            {{ status.construction_account.name }} ••{{ status.construction_account.account_number_last_four }}
            → {{ status.primary_checking_account?.name }} ••{{ status.primary_checking_account?.account_number_last_four }}
          </template>
          <template v-else>No construction account linked yet</template>
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-1.5">
        <UiBadge :data-testid="hook('state')" :tone="stateChip.tone">{{ stateChip.label }}</UiBadge>
        <RouterLink :data-testid="hook('open-deal')" :to="dealOnItsBoard('bought', status.bought_deal_id)"
                    class="inline-flex items-center gap-1 rounded-ctl px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10">
          <i class="pi pi-external-link text-[10px]" aria-hidden="true"></i>Open deal
        </RouterLink>
        <RouterLink v-if="status.is_in_the_liquidity_timeline" :data-testid="hook('show-on-timeline')" :to="dealOnTheLiquidityTimeline('bought', status.bought_deal_id)"
                    class="inline-flex items-center gap-1 rounded-ctl px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10">
          <i class="pi pi-chart-line text-[10px]" aria-hidden="true"></i>Show on the timeline
        </RouterLink>
        <a v-if="status.is_linked" :data-testid="hook('open-mercury')" :href="MERCURY_WEB_APP_URL" target="_blank" rel="noopener noreferrer"
           class="inline-flex items-center gap-1 rounded-ctl px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10">
          <i class="pi pi-building-columns text-[10px]" aria-hidden="true"></i>Open Mercury
        </a>
      </div>
    </header>

    <div v-if="status.needs_attention_because.length" :data-testid="hook('attention')" class="flex flex-wrap gap-2">
      <template v-for="reason in status.needs_attention_because" :key="reason">
        <button v-if="reason === 'deposit_due' && isLive" type="button" :data-testid="hook(`attention.${reason}`)" @click="emit('transfer', status, 'deposit')"
                class="inline-flex items-center gap-1.5 rounded-full border border-warning/40 bg-warning/10 px-3 py-1 text-xs font-medium text-warning hover:bg-warning/20">
          <i class="pi pi-exclamation-triangle text-[10px]" aria-hidden="true"></i>{{ ATTENTION_LABELS[reason] }} — deposit now
        </button>
        <RouterLink v-else-if="attentionLink(reason)" :data-testid="hook(`attention.${reason}`)" :to="attentionLink(reason)!"
                    class="inline-flex items-center gap-1.5 rounded-full border border-warning/40 bg-warning/10 px-3 py-1 text-xs font-medium text-warning hover:bg-warning/20">
          <i class="pi pi-exclamation-triangle text-[10px]" aria-hidden="true"></i>{{ ATTENTION_LABELS[reason] }} — see it on the timeline
        </RouterLink>
        <button v-else type="button" :data-testid="hook(`attention.${reason}`)" @click="refreshFromMercury"
                class="inline-flex items-center gap-1.5 rounded-full border border-warning/40 bg-warning/10 px-3 py-1 text-xs font-medium text-warning hover:bg-warning/20">
          <i class="pi pi-exclamation-triangle text-[10px]" aria-hidden="true"></i>{{ ATTENTION_LABELS[reason] }} — try again
        </button>
      </template>
    </div>

    <p v-if="errorMessage" :data-testid="hook('error')" role="alert" class="rounded-ctl border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">{{ errorMessage }}</p>

    <!-- Not linked yet: the plan, and the way to link -->
    <div v-if="!status.is_linked" class="space-y-3">
      <p class="text-sm text-fg-muted">
        Link this rehab's own Mercury account: the lender wires the draws there and the rehab is paid from it, so the timeline shows only your deposit and what comes back.
      </p>
      <UiButton :data-testid="hook('link')" @click="emit('link', status)"><i class="pi pi-link mr-1.5 text-xs" aria-hidden="true"></i>Link a construction account</UiButton>
    </div>

    <!-- Outcome and the account now (always open once linked) -->
    <div v-if="status.is_linked" class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <section :data-testid="hook('outcome')" aria-label="Outcome" class="space-y-2 rounded-ctl border border-line p-3">
        <h3 class="text-xs font-medium uppercase tracking-[0.12em] text-fg-muted">Outcome</h3>
        <ConstructionAccountFigure :testid="hook('projected-return')" label="Projected return at rehab end" :value="status.projected_return_at_rehab_end_dollars" emphasis
          :tone="(status.projected_return_at_rehab_end_dollars ?? 0) < 0 ? 'negative' : 'positive'"
          explanation="Balance + (budget − draws pulled) − (rehab cost − rehab paid)" />
        <ConstructionAccountFigure :testid="hook('own-money-back')" label="· your own money back" :value="status.own_money_back_at_rehab_end_dollars" />
        <ConstructionAccountFigure :testid="hook('spread-back')" label="· spread (stolen money)" :value="status.spread_at_rehab_end_dollars" />
        <ConstructionAccountFigure :testid="hook('safe-to-steal')" label="Safe to steal now" :value="status.safe_to_steal_now_dollars" emphasis
          :explanation="status.safe_to_steal_now_is_capped_by ? CAP_LABELS[status.safe_to_steal_now_is_capped_by] : undefined" />
        <ConstructionAccountFigure :testid="hook('top-up')" label="Top-up needed" :value="status.top_up_needed_dollars"
          :tone="(status.top_up_needed_dollars ?? 0) > 0 ? 'negative' : 'neutral'" explanation="Money to bring now so the account can pay what is left" />
      </section>
      <section :data-testid="hook('account-now')" aria-label="The account now" class="space-y-2 rounded-ctl border border-line p-3">
        <h3 class="text-xs font-medium uppercase tracking-[0.12em] text-fg-muted">The account now</h3>
        <ConstructionAccountFigure :testid="hook('balance')" label="Current balance" :value="status.current_balance_dollars" emphasis />
        <ConstructionAccountFigure :testid="hook('available')" label="Available balance" :value="status.available_balance_dollars" />
        <ConstructionAccountFigure :testid="hook('pending-in')" label="Pending money in" :value="status.pending_money_in_dollars" explanation="Accepted by the bank, not settled yet" />
        <ConstructionAccountFigure :testid="hook('pending-out')" label="Pending money out" :value="status.pending_money_out_dollars" />
        <ConstructionAccountFigure :testid="hook('checking-available')" label="Checking available" :value="status.primary_checking_available_balance_dollars"
          explanation="Where a deposit comes from and a steal goes to" />
        <div class="flex flex-wrap items-center justify-between gap-2 pt-1 text-xs text-fg-muted">
          <span :data-testid="hook('as-of')">Amounts as of {{ shortDateTime(status.amounts_as_of) }}</span>
          <UiButton variant="ghost" size="sm" :data-testid="hook('refresh')" :loading="savingFigure === 'refresh'" @click="refreshFromMercury">Refresh</UiButton>
        </div>
      </section>
    </div>

    <!-- Move money: the app asks Mercury (each one asks for your passkey) -->
    <div v-if="isLive" :data-testid="hook('transfer-actions')" class="flex flex-wrap gap-2">
      <UiButton size="sm" :data-testid="hook('deposit')" @click="emit('transfer', status, 'deposit')">
        <i class="pi pi-arrow-down mr-1.5 text-xs" aria-hidden="true"></i>Deposit
      </UiButton>
      <UiButton size="sm" variant="secondary" :data-testid="hook('steal')" @click="emit('transfer', status, 'steal')">
        <i class="pi pi-arrow-up mr-1.5 text-xs" aria-hidden="true"></i>Steal
      </UiButton>
      <UiButton size="sm" variant="secondary" :data-testid="hook('close-out')" @click="emit('transfer', status, 'close_out')">Close out</UiButton>
    </div>

    <!-- Rehab: the deal's own figures, editable here (written to the Bought deal) -->
    <details :data-testid="hook('rehab')" class="group rounded-ctl border border-line" :open="!status.is_linked">
      <summary class="flex cursor-pointer items-center justify-between px-3 py-2 text-sm font-medium text-fg">
        Rehab <span class="numeric text-fg-muted">{{ formatMoney(status.rehab_cost_dollars) }} of {{ formatMoney(status.construction_budget_dollars) }}</span>
      </summary>
      <div class="space-y-2 border-t border-line p-3">
        <ConstructionAccountEditableFigure :testid="hook('actual-rehab-cost')" label="Actual rehab cost" :value="status.actual_rehab_cost_dollars"
          :is-saving="savingFigure === 'actual-rehab-cost'" explanation="Before the contingency. Saved on the Bought deal too."
          @save="value => saveRehabFigure('actual-rehab-cost', { actual_rehab_cost_dollars: value }, 'Change the actual rehab cost')" />
        <ConstructionAccountEditableFigure :testid="hook('contingency')" label="Contingency" unit="percent" :value="status.rehab_contingency_percent"
          :is-saving="savingFigure === 'contingency'"
          @save="value => saveRehabFigure('contingency', { rehab_contingency_percent: value }, 'Change the rehab contingency')" />
        <ConstructionAccountFigure :testid="hook('rehab-cost')" label="Rehab cost" :value="status.rehab_cost_dollars" explanation="Actual rehab cost + contingency. Appliances are not part of it." />
        <ConstructionAccountEditableFigure :testid="hook('construction-budget')" label="Construction budget" :value="status.construction_budget_dollars"
          :is-saving="savingFigure === 'construction-budget'" explanation="The lender's construction loan budget"
          @save="value => saveRehabFigure('construction-budget', { construction_budget_dollars: value }, 'Change the construction budget')" />
        <ConstructionAccountFigure :testid="hook('original-steal')" :label="rehabIsOverBudget ? 'Rehab beyond the budget' : 'Spread (budget − rehab cost)'"
          :value="Math.abs(status.original_steal_dollars)" :tone="rehabIsOverBudget ? 'warning' : 'positive'" />
      </div>
    </details>

    <!-- Your own money: the cushion is the one deposit figure -->
    <details :data-testid="hook('own-money')" class="rounded-ctl border border-line" open>
      <summary class="flex cursor-pointer items-center justify-between px-3 py-2 text-sm font-medium text-fg">
        Your own money <span class="numeric text-fg-muted">{{ formatMoney(status.total_to_deposit_dollars) }} to deposit</span>
      </summary>
      <div class="space-y-2 border-t border-line p-3">
        <ConstructionAccountEditableFigure :testid="hook('cushion')" label="Rehab cushion (what you deposit)" :value="status.rehab_cushion_dollars"
          :is-saving="savingFigure === 'cushion'" :explanation="`Suggested ${formatMoney(status.suggested_rehab_cushion_dollars)}. Saved on the Bought deal too.`"
          @save="value => saveRehabFigure('cushion', { rehab_cushion_dollars: value }, 'Change the rehab cushion')" />
        <div class="flex justify-end">
          <UiButton v-if="status.rehab_cushion_dollars !== status.suggested_rehab_cushion_dollars" variant="ghost" size="sm" :data-testid="hook('cushion.reset')"
                    @click="saveRehabFigure('cushion', { rehab_cushion_dollars: status.suggested_rehab_cushion_dollars }, 'Reset the rehab cushion to the suggested amount')">
            Reset to suggested ({{ formatMoney(status.suggested_rehab_cushion_dollars) }})
          </UiButton>
        </div>
        <ConstructionAccountFigure :testid="hook('total-to-deposit')" label="Total to deposit" :value="status.total_to_deposit_dollars"
          :explanation="rehabIsOverBudget ? `Cushion ${formatMoney(status.rehab_cushion_dollars)} + rehab beyond the budget ${formatMoney(status.rehab_beyond_the_construction_budget_dollars)}` : 'The cushion'" />
        <template v-if="status.is_linked">
          <ConstructionAccountFigure :testid="hook('deposited')" label="Deposited so far" :value="status.own_money_transferred_into_the_account_dollars" />
          <ConstructionAccountFigure :testid="hook('remaining-deposit')" label="Remaining deposit" :value="status.remaining_deposit_dollars"
            :tone="(status.remaining_deposit_dollars ?? 0) > 0 ? 'warning' : 'neutral'" />
          <ConstructionAccountFigure :testid="hook('stolen')" label="Stolen so far" :value="status.own_money_transferred_out_of_the_account_dollars" />
          <ConstructionAccountFigure :testid="hook('own-money-inside')" label="Your own money still in the account" :value="status.own_money_still_in_the_account_dollars"
            explanation="Deposited − stolen" />
          <ConstructionAccountFigure :testid="hook('spread-taken')" label="Spread already taken" :value="status.spread_already_taken_dollars" />
          <ConstructionAccountEditableFigure :testid="hook('buffer')" label="Buffer to keep in the account" :value="status.minimum_balance_to_keep_in_construction_account_dollars ?? 0"
            :is-saving="savingFigure === 'buffer'" explanation="For reimbursement draws: lowers what is safe to steal"
            @save="value => saveLinkFigure('buffer', { minimum_balance_to_keep_in_construction_account_dollars: value }, 'Change the buffer to keep')" />
        </template>
      </div>
    </details>

    <template v-if="status.is_linked">
      <!-- Loan draws and rehab paid, each by its source -->
      <details :data-testid="hook('draws')" class="rounded-ctl border border-line">
        <summary class="flex cursor-pointer items-center justify-between px-3 py-2 text-sm font-medium text-fg">
          Loan draws <span class="numeric text-fg-muted">{{ formatMoney(status.loan_draws_pulled?.total_dollars) }} pulled · {{ percent(status.percent_of_the_construction_budget_pulled) }}</span>
        </summary>
        <div class="space-y-2 border-t border-line p-3">
          <ConstructionAccountFigure :testid="hook('draws-pulled')" label="Pulled until now" :value="status.loan_draws_pulled?.total_dollars" :explanation="sourceLine(status.loan_draws_pulled)" />
          <ConstructionAccountFigure :testid="hook('draws-remaining')" label="Remaining to pull" :value="status.loan_draws_remaining_to_pull_dollars" />
          <ConstructionAccountFigure :testid="hook('draw-count')" label="Number of draws" :value="status.loan_draw_count != null ? String(status.loan_draw_count) : null" />
          <ConstructionAccountFigure :testid="hook('last-draw')" label="Last draw"
            :value="status.last_loan_draw ? `${formatMoney(status.last_loan_draw.amount_dollars)} on ${status.last_loan_draw.date}` : null" />
        </div>
      </details>

      <details :data-testid="hook('paid')" class="rounded-ctl border border-line">
        <summary class="flex cursor-pointer items-center justify-between px-3 py-2 text-sm font-medium text-fg">
          Rehab paid <span class="numeric text-fg-muted">{{ formatMoney(status.rehab_payments_made?.total_dollars) }} · {{ percent(status.percent_of_the_rehab_paid) }}</span>
        </summary>
        <div class="space-y-2 border-t border-line p-3">
          <ConstructionAccountFigure :testid="hook('paid-until-now')" label="Paid until now" :value="status.rehab_payments_made?.total_dollars" :explanation="sourceLine(status.rehab_payments_made)" />
          <ConstructionAccountFigure :testid="hook('unpaid')" label="Unpaid remaining" :value="status.unpaid_rehab_remaining_dollars" />
          <ConstructionAccountFigure :testid="hook('last-payment')" label="Last payment"
            :value="status.last_rehab_payment ? `${formatMoney(status.last_rehab_payment.amount_dollars)} to ${status.last_rehab_payment.counterparty_name} on ${status.last_rehab_payment.date}` : null" />
          <div v-if="status.rehab_paid_by_payee.length">
            <p class="mb-1 text-xs text-fg-muted">Paid per payee</p>
            <ul :data-testid="hook('paid-by-payee')" class="divide-y divide-line rounded-ctl border border-line">
              <li v-for="payee in status.rehab_paid_by_payee" :key="payee.payee_name" class="flex justify-between px-3 py-1.5 text-sm">
                <span class="text-fg">{{ payee.payee_name }}</span><span class="numeric">{{ formatMoney(payee.amount_dollars) }}</span>
              </li>
            </ul>
          </div>
        </div>
      </details>

      <!-- Before this account: always editable -->
      <details :data-testid="hook('before')" class="rounded-ctl border border-line">
        <summary class="flex cursor-pointer items-center justify-between px-3 py-2 text-sm font-medium text-fg">Before this account</summary>
        <div class="space-y-2 border-t border-line p-3">
          <ConstructionAccountEditableFigure :testid="hook('draws-before')" label="Loan draws pulled before" :value="status.loan_draws_pulled_before_construction_account_dollars ?? 0"
            :is-saving="savingFigure === 'draws-before'" explanation="Draws that landed somewhere else before this account existed"
            @save="value => saveLinkFigure('draws-before', { loan_draws_pulled_before_construction_account_dollars: value }, 'Change the draws pulled before this account')" />
          <ConstructionAccountEditableFigure :testid="hook('paid-before')" label="Rehab paid before" :value="status.rehab_payments_made_before_construction_account_dollars ?? 0"
            :is-saving="savingFigure === 'paid-before'" explanation="Rehab paid from somewhere else before this account existed"
            @save="value => saveLinkFigure('paid-before', { rehab_payments_made_before_construction_account_dollars: value }, 'Change the rehab paid before this account')" />
        </div>
      </details>

      <!-- By hand, and the bank feed -->
      <details :data-testid="hook('manual-entries-section')" class="rounded-ctl border border-line" :open="manualEntriesOpen" @toggle="manualEntriesOpen = ($event.target as HTMLDetailsElement).open">
        <summary class="flex cursor-pointer items-center justify-between px-3 py-2 text-sm font-medium text-fg">
          Entered by hand <span class="text-xs text-fg-muted">{{ status.manual_adjustments.length }}</span>
        </summary>
        <div class="border-t border-line p-3">
          <ConstructionAccountManualAdjustmentsList :bought-deal-id="status.bought_deal_id" :adjustments="status.manual_adjustments" @error="message => (errorMessage = message)" />
        </div>
      </details>

      <details :data-testid="hook('transactions-section')" class="rounded-ctl border border-line" :open="transactionsOpen" @toggle="transactionsOpen = ($event.target as HTMLDetailsElement).open">
        <summary class="flex cursor-pointer items-center justify-between px-3 py-2 text-sm font-medium text-fg">
          Bank transactions
          <span class="text-xs text-fg-muted">{{ status.transactions_counted_count ?? 0 }} counted · {{ status.transactions_ignored_count ?? 0 }} ignored ·
            {{ status.transactions_recategorised_count ?? 0 }} re-categorised · {{ status.transactions_failed_or_cancelled_count ?? 0 }} failed</span>
        </summary>
        <div class="border-t border-line p-3">
          <p class="mb-2 text-xs text-fg-muted">Last transaction: {{ status.last_transaction_date ?? 'none yet' }}</p>
          <ConstructionAccountTransactionsList v-if="transactionsOpen" :bought-deal-id="status.bought_deal_id" @error="message => (errorMessage = message)" />
        </div>
      </details>
    </template>

    <!-- Transfers made in the app -->
    <details v-if="status.is_linked" :data-testid="hook('transfers')" class="rounded-ctl border border-line">
      <summary class="flex cursor-pointer items-center justify-between px-3 py-2 text-sm font-medium text-fg">
        Transfers made in the app <span class="text-xs text-fg-muted">{{ status.transfers_made_in_the_app.length }}</span>
      </summary>
      <div class="space-y-2 border-t border-line p-3 text-sm">
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
              <UiBadge :tone="TRANSFER_OUTCOME_TONES[transfer.transfer_outcome]" class="ml-1">{{ TRANSFER_OUTCOME_LABELS[transfer.transfer_outcome] }}<template v-if="transfer.mercury_refusal_http_status"> ({{ transfer.mercury_refusal_http_status }})</template></UiBadge>
              <span v-if="transfer.transfer_outcome === 'accepted_by_mercury'" class="ml-1 text-xs text-fg-muted">
                {{ transfer.is_in_the_bank_feed ? 'in the bank feed' : 'not in the bank feed yet' }}
              </span>
            </span>
            <span class="numeric font-semibold">{{ formatMoney(transfer.amount_dollars) }}</span>
          </li>
        </ul>
      </div>
    </details>

    <!-- On the timeline, and what is not in this account -->
    <details :data-testid="hook('timeline-rows')" class="rounded-ctl border border-line">
      <summary class="flex cursor-pointer items-center justify-between px-3 py-2 text-sm font-medium text-fg">On the timeline</summary>
      <div class="space-y-1 border-t border-line p-3">
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
          Rehab completed {{ status.rehab_completed_date }}{{ status.rehab_completed_is_approved ? ' (approved)' : '' }} ·
          refi {{ status.refi_closing_date }}{{ status.refi_closed_is_approved ? ' (approved)' : '' }} — change them from the timeline's deal entry.
        </p>
      </div>
    </details>

    <!-- History and the account's own actions -->
    <footer v-if="status.is_linked" class="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
      <span :data-testid="hook('history')" class="text-xs text-fg-muted">
        <template v-if="status.previous_construction_mercury_account_ids.length">Earlier accounts: {{ status.previous_construction_mercury_account_ids.length }}</template>
        <template v-if="status.marked_ready_for_close_out_at"> · Ready for close-out</template>
        <template v-if="status.closed_out_at"> · Closed out {{ shortDateTime(status.closed_out_at) }}</template>
      </span>
      <div class="flex flex-wrap gap-2">
        <UiButton variant="ghost" size="sm" :data-testid="hook('edit-link')" @click="emit('link', status)">Account settings</UiButton>
        <UiButton v-if="isLive" variant="ghost" size="sm" :data-testid="hook('switch')" @click="emit('switchAccount', status)">Switch account</UiButton>
        <UiButton v-if="isLive && !status.marked_ready_for_close_out_at" variant="ghost" size="sm" :data-testid="hook('mark-ready')" @click="markReadyForCloseOut">Mark ready for close-out</UiButton>
        <UiButton v-if="isLive" variant="secondary" size="sm" :data-testid="hook('mark-closed-out')" @click="markClosedOut">Mark closed out</UiButton>
        <UiButton v-if="status.closed_out_at" variant="secondary" size="sm" :data-testid="hook('reopen')" @click="reopen">Reopen</UiButton>
        <UiButton variant="danger" size="sm" :data-testid="hook('unlink')" @click="unlink">Unlink</UiButton>
      </div>
    </footer>
  </UiSurface>
</template>
