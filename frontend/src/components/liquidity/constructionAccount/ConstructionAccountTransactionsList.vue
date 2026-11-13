<script setup lang="ts">
/**
 * The construction account's bank transactions (tasks/todo/ConstructionAccountPerRehab.md), newest first, each with
 * what it counts as: a loan draw, a rehab payment, your own money, or nothing (ignored, or failed at the bank). Ignore
 * one, count it as something else, add a note, or put it back on its automatic category; each change goes through the
 * timeline prompt.
 */
import { computed, onMounted, ref } from 'vue'

import { useConstructionAccountStore } from '../../../stores/constructionAccountStore'
import type { ConstructionAccountTransaction, ConstructionAccountTransactionCategory } from '../../../types/constructionAccount'
import { formatSignedMoney } from '../../../utils/money'

const props = defineProps<{ boughtDealId: string }>()
const emit = defineEmits<{ (e: 'error', message: string): void }>()

const store = useConstructionAccountStore()
const CATEGORY_LABELS: Record<ConstructionAccountTransactionCategory, string> = {
  loan_draw: 'Loan draw', rehab_payment: 'Rehab payment', own_money: 'Your own money',
}
type Filter = 'all' | ConstructionAccountTransactionCategory | 'ignored'
const FILTERS: { value: Filter; label: string }[] = [
  { value: 'all', label: 'All' }, { value: 'loan_draw', label: 'Draws' }, { value: 'rehab_payment', label: 'Payments' },
  { value: 'own_money', label: 'Own money' }, { value: 'ignored', label: 'Ignored' },
]
const filter = ref<Filter>('all')
const isLoading = ref(false)
const loadFailed = ref(false)
const noteDraftById = ref<Record<string, string>>({})

const transactions = computed(() => store.transactionsByDealId[props.boughtDealId] ?? [])
const shownTransactions = computed(() => transactions.value.filter(transaction =>
  filter.value === 'all' ? true : filter.value === 'ignored' ? transaction.ignored : transaction.effective_category === filter.value && !transaction.ignored))

async function load() {
  isLoading.value = true
  loadFailed.value = false
  try {
    await store.loadTransactions(props.boughtDealId)
  } catch {
    loadFailed.value = true
  } finally {
    isLoading.value = false
  }
}
onMounted(load)

function errorMessageOf(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : 'The change could not be saved.'
}

async function setOverride(transaction: ConstructionAccountTransaction, change: { ignored?: boolean; category_override?: ConstructionAccountTransactionCategory | null; note?: string | null }) {
  try {
    await store.setTransactionOverride(props.boughtDealId, transaction.mercury_transaction_id, {
      ignored: change.ignored ?? transaction.ignored,
      category_override: change.category_override === undefined ? transaction.category_override : change.category_override,
      note: change.note === undefined ? transaction.note : change.note,
    })
  } catch (error) {
    emit('error', errorMessageOf(error))
  }
}

async function restoreAutomatic(transaction: ConstructionAccountTransaction) {
  try {
    await store.clearTransactionOverride(props.boughtDealId, transaction.mercury_transaction_id)
  } catch (error) {
    emit('error', errorMessageOf(error))
  }
}

function onCategoryChange(transaction: ConstructionAccountTransaction, event: Event) {
  const value = (event.target as HTMLSelectElement).value as ConstructionAccountTransactionCategory
  void setOverride(transaction, { category_override: value === transaction.automatic_category ? null : value })
}

function hasAnOverride(transaction: ConstructionAccountTransaction): boolean {
  return transaction.ignored || transaction.category_override !== null || !!transaction.note
}
</script>

<template>
  <div :data-testid="`ca.${boughtDealId}.transactions`" class="space-y-2">
    <div class="flex flex-wrap items-center gap-2">
      <UiSegmented :model-value="filter" :options="FILTERS" ariaLabel="Show transactions" size="sm" @update:model-value="value => (filter = value as Filter)" />
      <UiButton variant="ghost" size="sm" :data-testid="`ca.${boughtDealId}.transactions.reload`" :loading="isLoading" @click="load">Reload</UiButton>
    </div>
    <p v-if="loadFailed" role="alert" class="text-xs text-negative">The bank transactions could not be read from Mercury. Try again in a moment.</p>
    <p v-else-if="!isLoading && !shownTransactions.length" class="text-xs text-fg-muted">No transactions here.</p>
    <ul v-if="shownTransactions.length" class="divide-y divide-line rounded-ctl border border-line">
      <li v-for="transaction in shownTransactions" :key="transaction.mercury_transaction_id"
          :data-testid="`ca.${boughtDealId}.transaction.${transaction.mercury_transaction_id}`"
          class="space-y-1.5 px-3 py-2 text-sm" :class="transaction.ignored || !transaction.effective_category ? 'opacity-60' : ''">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <span class="min-w-0">
            <span class="text-fg">{{ transaction.counterparty_name || 'Unnamed' }}</span>
            <span class="ml-2 text-xs text-fg-muted">{{ transaction.transaction_date ?? 'no date' }}</span>
            <UiBadge v-if="transaction.is_pending" tone="info" class="ml-2">Pending</UiBadge>
            <UiBadge v-if="transaction.bank_status === 'failed' || transaction.bank_status === 'cancelled'" tone="negative" class="ml-2">{{ transaction.bank_status }}</UiBadge>
            <UiBadge v-if="transaction.ignored" tone="warning" class="ml-2">Ignored</UiBadge>
          </span>
          <span class="numeric font-semibold" :class="transaction.signed_amount_dollars > 0 ? 'text-positive' : 'text-fg'">{{ formatSignedMoney(transaction.signed_amount_dollars) }}</span>
        </div>
        <div class="flex flex-wrap items-center gap-2 text-xs">
          <label class="flex items-center gap-1 text-fg-muted">Counts as
            <select :value="transaction.category_override ?? transaction.automatic_category" :disabled="transaction.ignored"
                    :data-testid="`ca.${boughtDealId}.transaction.${transaction.mercury_transaction_id}.category`"
                    class="ui-input h-8 py-0 text-xs" @change="onCategoryChange(transaction, $event)">
              <option v-for="(label, category) in CATEGORY_LABELS" :key="category" :value="category">
                {{ label }}{{ category === transaction.automatic_category ? ' (automatic)' : '' }}
              </option>
            </select>
          </label>
          <UiButton variant="ghost" size="sm" :data-testid="`ca.${boughtDealId}.transaction.${transaction.mercury_transaction_id}.ignore`"
                    @click="setOverride(transaction, { ignored: !transaction.ignored })">
            {{ transaction.ignored ? 'Count it again' : 'Ignore' }}
          </UiButton>
          <input v-model="noteDraftById[transaction.mercury_transaction_id]" :placeholder="transaction.note ?? 'Add a note'" maxlength="500"
                 :data-testid="`ca.${boughtDealId}.transaction.${transaction.mercury_transaction_id}.note`" class="ui-input h-8 min-w-0 flex-1 py-0 text-xs"
                 @keydown.enter.prevent="setOverride(transaction, { note: noteDraftById[transaction.mercury_transaction_id]?.trim() || null })" />
          <UiButton v-if="hasAnOverride(transaction)" variant="ghost" size="sm"
                    :data-testid="`ca.${boughtDealId}.transaction.${transaction.mercury_transaction_id}.restore`" @click="restoreAutomatic(transaction)">
            Restore automatic
          </UiButton>
        </div>
      </li>
    </ul>
  </div>
</template>
