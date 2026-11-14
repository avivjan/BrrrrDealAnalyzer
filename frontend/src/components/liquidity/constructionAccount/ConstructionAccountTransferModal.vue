<script setup lang="ts">
/**
 * Deposit, Steal and Close out (tasks/todo/ConstructionAccountPerRehab.md, Step E): the app moves money at Mercury
 * between the rehab's construction account and the same LLC's checking. This window is the confirmation: the amount,
 * the timeline rows before -> after (a preview: Mercury is asked nothing), and one button that sends it. Sending asks
 * for your passkey.
 *
 * One idempotency key per open window: sending twice (a double tap, the passkey retry) never makes two transfers.
 * Close out steals the whole available balance, then marks the account closed out (its return row is marked done).
 */
import { computed, ref, watch } from 'vue'

import { constructionAccountApi } from '../../../api/constructionAccount'
import { figureChangesBetween, useConstructionAccountStore } from '../../../stores/constructionAccountStore'
import type { ConstructionAccountStatus, ConstructionAccountTransfer, ConstructionAccountTransferWriteResult } from '../../../types/constructionAccount'
import {
  checkTransfer, suggestedTransferAmount, type ConstructionAccountTransferKind,
} from '../../../utils/constructionAccountTransferRules'
import { todayISO } from '../../../utils/liquidityEngine'
import { formatMoney } from '../../../utils/money'
import DealCashRowChangesList from '../DealCashRowChangesList.vue'

const props = defineProps<{
  open: boolean
  status: ConstructionAccountStatus | null
  kind: ConstructionAccountTransferKind
}>()

const emit = defineEmits<{
  (e: 'close'): void
  /** Mercury accepted it: the page reads the bank in a burst until the feed shows it. */
  (e: 'transferred', transfer: ConstructionAccountTransfer): void
}>()

const TITLES: Record<ConstructionAccountTransferKind, string> = {
  deposit: 'Deposit into the construction account',
  steal: 'Steal to checking',
  close_out: 'Close the construction account out',
}

const store = useConstructionAccountStore()
const amountText = ref('')
const idempotencyKey = ref('')
const confirmTheTopUp = ref(false)
const preview = ref<ConstructionAccountTransferWriteResult | null>(null)
const isPreviewing = ref(false)
const isSending = ref(false)
const errorMessage = ref<string | null>(null)
const sentTransfer = ref<ConstructionAccountTransfer | null>(null)
let previewTimer: ReturnType<typeof setTimeout> | null = null
let previewRequestNumber = 0

const amountDollars = computed(() => Number(amountText.value.replace(/[$,\s]/g, '')))
const check = computed(() => props.status ? checkTransfer(props.status, props.kind, amountDollars.value) : null)
const needsTheTopUpConfirmation = computed(() => (check.value?.amountAboveSafeToStealDollars ?? 0) > 0)
const canSend = computed(() => !!check.value && !check.value.blockingProblems.length && !isSending.value && !sentTransfer.value
  && (!needsTheTopUpConfirmation.value || confirmTheTopUp.value))
const figureChanges = computed(() => preview.value ? figureChangesBetween(preview.value.status_before, preview.value.status_after) : [])
const rowChanges = computed(() => preview.value?.liquidity_row_changes?.changes ?? [])
const sourceAndDestination = computed(() => {
  const construction = props.status?.construction_account?.name ?? 'the construction account'
  const checking = props.status?.primary_checking_account?.name ?? 'checking'
  return props.kind === 'deposit' ? `${checking} → ${construction}` : `${construction} → ${checking}`
})

function newIdempotencyKey(): string {
  return typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID() : `transfer-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`
}

function errorMessageOf(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : 'That did not work. Nothing was sent.'
}

function send(options: { previewOnly?: boolean }) {
  const status = props.status!
  const data = { amount_dollars: amountDollars.value, idempotency_key: idempotencyKey.value, confirm_amount_exceeds_safe_to_steal: confirmTheTopUp.value }
  const write = { previewOnly: options.previewOnly, today: todayISO() }
  return props.kind === 'deposit'
    ? constructionAccountApi.deposit(status.bought_deal_id, data, write)
    : constructionAccountApi.steal(status.bought_deal_id, data, write)
}

async function loadPreview() {
  if (!props.status || check.value?.blockingProblems.length) {
    preview.value = null
    return
  }
  const requestNumber = ++previewRequestNumber
  isPreviewing.value = true
  try {
    const answer = await send({ previewOnly: true })
    if (requestNumber === previewRequestNumber) {
      preview.value = answer
      errorMessage.value = null
    }
  } catch (error) {
    if (requestNumber === previewRequestNumber) {
      preview.value = null
      errorMessage.value = errorMessageOf(error)
    }
  } finally {
    if (requestNumber === previewRequestNumber) isPreviewing.value = false
  }
}

watch(() => [props.open, props.status?.bought_deal_id, props.kind] as const, ([open]) => {
  if (!open || !props.status) return
  idempotencyKey.value = newIdempotencyKey()
  amountText.value = String(suggestedTransferAmount(props.status, props.kind))
  confirmTheTopUp.value = false
  sentTransfer.value = null
  errorMessage.value = null
  preview.value = null
  void loadPreview()
}, { immediate: true })

watch(amountText, () => {
  if (!props.open || sentTransfer.value) return
  confirmTheTopUp.value = false
  if (previewTimer) clearTimeout(previewTimer)
  previewTimer = setTimeout(() => { void loadPreview() }, 400)
})

const OUTCOME_MESSAGES: Record<ConstructionAccountTransfer['transfer_outcome'], string> = {
  accepted_by_mercury: 'Mercury accepted the transfer. The timeline counts it now; the bank feed will show it shortly.',
  waiting_for_approval_in_mercury: 'Mercury created the transfer request. Approve it in Mercury; the timeline counts it once Mercury sends it.',
  being_sent: 'The transfer is being sent.',
  refused_by_mercury: 'Mercury refused the transfer. Nothing was sent.',
  mercury_did_not_answer: 'Mercury did not answer. The transfer may have been made: check Mercury before trying again.',
  failed_or_cancelled_at_mercury: 'Mercury says the transfer failed or was cancelled. Nothing moved.',
}
/** Why Mercury refused, from the HTTP status it answered (never Mercury's own text). */
function refusalHintOf(httpStatus: number | null | undefined): string {
  if (httpStatus === 401 || httpStatus === 403) {
    return ` Mercury answered ${httpStatus}: the transfer token is not allowed. In Mercury → Settings → API → Tokens, check that it can make transfers and that its allowed IPs include the server's.`
  }
  if (httpStatus === 400 || httpStatus === 422) return ` Mercury answered ${httpStatus}: it did not accept the request.`
  if (httpStatus === 429) return ' Mercury answered 429: it asked to slow down. Try again in a few minutes.'
  return httpStatus ? ` Mercury answered ${httpStatus}.` : ''
}
const outcomeMessage = computed(() => {
  const transfer = sentTransfer.value
  if (!transfer) return null
  const message = OUTCOME_MESSAGES[transfer.transfer_outcome]
  return transfer.transfer_outcome === 'refused_by_mercury' ? message + refusalHintOf(transfer.mercury_refusal_http_status) : message
})
const outcomeTone = computed(() => ['accepted_by_mercury', 'waiting_for_approval_in_mercury'].includes(sentTransfer.value?.transfer_outcome ?? '') ? 'positive' : 'warning')

async function sendTheTransfer() {
  if (!canSend.value || !props.status) return
  isSending.value = true
  errorMessage.value = null
  try {
    const answer = await send({})
    sentTransfer.value = answer.transfer
    if (answer.transfer?.transfer_outcome === 'accepted_by_mercury') {
      if (props.kind === 'close_out') await constructionAccountApi.markClosedOut(props.status.bought_deal_id, { today: todayISO() })
      emit('transferred', answer.transfer)
    }
    await store.reloadWhatShowsTheSameData(props.status.bought_deal_id, false)
  } catch (error) {
    errorMessage.value = errorMessageOf(error)
  } finally {
    isSending.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open && status" data-testid="ca-transfer.root" :data-kind="kind" class="fixed inset-0 z-50 flex items-center justify-center p-4"
           @keydown.escape="emit('close')">
        <div class="absolute inset-0 bg-fg/50 md:backdrop-blur-sm" @click="emit('close')" />
        <UiModalPanel size="lg" labelled-by="ca-transfer-title" class="modal-panel relative">
          <template #header>
            <div>
              <h2 id="ca-transfer-title" class="font-display text-lg font-semibold tracking-display text-fg">{{ TITLES[kind] }}</h2>
              <p data-testid="ca-transfer.accounts" class="mt-1 text-sm text-fg-muted">{{ status.deal_address }} · {{ sourceAndDestination }}</p>
            </div>
          </template>

          <div class="space-y-4">
            <UiField>
              <template #label>Amount</template>
              <template #default="{ id }">
                <input :id="id" v-model="amountText" data-testid="ca-transfer.amount" inputmode="decimal" class="ui-input numeric"
                       :disabled="!!sentTransfer || isSending" />
              </template>
            </UiField>
            <p class="text-xs text-fg-muted">
              <template v-if="kind === 'deposit'">Still to deposit {{ formatMoney(status.remaining_deposit_dollars) }} · checking available {{ formatMoney(status.primary_checking_available_balance_dollars) }}</template>
              <template v-else>Safe to steal now {{ formatMoney(status.safe_to_steal_now_dollars) }} · available in the account {{ formatMoney(status.available_balance_dollars) }}</template>
              · {{ status.transfers_left_this_hour ?? '—' }} transfers left this hour · at most {{ formatMoney(status.maximum_single_transfer_dollars) }} each
            </p>
            <p v-if="kind === 'close_out'" class="text-sm text-fg">Then the account is marked closed out, its return row is marked done, and the rehab summary (every number, draw, payment and transaction) is e-mailed to you and saved to your Google Drive.</p>

            <ul v-if="check?.blockingProblems.length && !sentTransfer" data-testid="ca-transfer.problems" role="alert"
                class="space-y-1 rounded-ctl border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">
              <li v-for="problem in check.blockingProblems" :key="problem">{{ problem }}</li>
            </ul>

            <div v-if="needsTheTopUpConfirmation && !check?.blockingProblems.length && !sentTransfer" data-testid="ca-transfer.top-up-warning"
                 class="space-y-2 rounded-ctl border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
              <p>This is {{ formatMoney(check!.amountAboveSafeToStealDollars) }} above safe to steal now: you will need to top up the account by about that much before the rehab ends.</p>
              <label class="flex items-center gap-2 text-fg">
                <input v-model="confirmTheTopUp" data-testid="ca-transfer.confirm-top-up" type="checkbox" />
                I will top it up later
              </label>
            </div>

            <p v-if="errorMessage" data-testid="ca-transfer.error" role="alert" class="rounded-ctl border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">{{ errorMessage }}</p>
            <p v-if="outcomeMessage" data-testid="ca-transfer.outcome" :data-outcome="sentTransfer?.transfer_outcome" role="status"
               :class="outcomeTone === 'positive' ? 'border-positive/40 bg-positive/10 text-positive' : 'border-warning/40 bg-warning/10 text-warning'"
               class="rounded-ctl border px-3 py-2 text-sm">{{ outcomeMessage }}</p>

            <template v-if="preview && !sentTransfer">
              <section v-if="figureChanges.length" data-testid="ca-transfer.figures" aria-label="Figures that change">
                <h3 class="mb-2 text-xs font-medium uppercase tracking-[0.12em] text-fg-muted">Figures</h3>
                <ul class="divide-y divide-line rounded-ctl border border-line">
                  <li v-for="figure in figureChanges" :key="figure.label" class="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm">
                    <span class="text-fg">{{ figure.label }}</span>
                    <span class="numeric text-fg-muted"><s>{{ figure.before }}</s> <i class="pi pi-arrow-right mx-1 text-[10px]" aria-hidden="true"></i><span class="font-semibold text-fg">{{ figure.after }}</span></span>
                  </li>
                </ul>
              </section>
              <section v-if="preview.row_descriptions_marked_done.length" data-testid="ca-transfer.marked-done" aria-label="Rows marked done">
                <h3 class="mb-2 text-xs font-medium uppercase tracking-[0.12em] text-fg-muted">Marked done</h3>
                <ul class="space-y-1 text-sm text-fg">
                  <li v-for="description in preview.row_descriptions_marked_done" :key="description"><i class="pi pi-check mr-1.5 text-xs text-positive" aria-hidden="true"></i>{{ description }}</li>
                </ul>
              </section>
              <section v-if="rowChanges.length" data-testid="ca-transfer.rows" aria-label="Timeline rows">
                <h3 class="mb-2 text-xs font-medium uppercase tracking-[0.12em] text-fg-muted">Timeline rows</h3>
                <DealCashRowChangesList :changes="rowChanges" :use-deal-value-for="[]" />
              </section>
              <p v-if="!preview.changes_the_liquidity_timeline" class="text-xs text-fg-muted">No timeline row changes.</p>
            </template>
            <p v-else-if="isPreviewing" data-testid="ca-transfer.loading" class="text-sm text-fg-muted">Reading what this changes…</p>
          </div>

          <template #footer>
            <div class="flex justify-end gap-3">
              <UiButton data-testid="ca-transfer.close" variant="ghost" :disabled="isSending" @click="emit('close')">{{ sentTransfer ? 'Close' : 'Cancel' }}</UiButton>
              <UiButton v-if="!sentTransfer" data-testid="ca-transfer.send" variant="primary" :disabled="!canSend" :loading="isSending" @click="sendTheTransfer">
                {{ kind === 'deposit' ? 'Deposit' : kind === 'steal' ? 'Steal' : 'Steal and close out' }} {{ formatMoney(amountDollars || 0) }}
              </UiButton>
            </div>
          </template>
        </UiModalPanel>
      </div>
    </Transition>
  </Teleport>
</template>
