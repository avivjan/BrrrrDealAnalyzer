<script setup lang="ts">
/**
 * Rehab money that never touched the construction account (tasks/todo/ConstructionAccountPerRehab.md): a payment
 * made from another account, by card or in cash, or a draw the lender wired elsewhere. Add, edit and delete; each
 * save goes through the timeline prompt.
 */
import { ref } from 'vue'

import { useConstructionAccountStore } from '../../../stores/constructionAccountStore'
import type { ConstructionAccountManualAdjustment, ConstructionAccountManualAdjustmentType } from '../../../types/constructionAccount'
import { todayISO } from '../../../utils/liquidityEngine'
import { formatMoney } from '../../../utils/money'

const props = defineProps<{ boughtDealId: string; adjustments: ConstructionAccountManualAdjustment[] }>()
const emit = defineEmits<{ (e: 'error', message: string): void }>()

const store = useConstructionAccountStore()
const TYPE_LABELS: Record<ConstructionAccountManualAdjustmentType, string> = {
  manual_payment: 'Payment made outside the account',
  manual_draw: 'Draw received outside the account',
}

interface Draft { id: string | null; adjustment_type: ConstructionAccountManualAdjustmentType; amount: string; date: string; note: string }
const draft = ref<Draft | null>(null)
const isSaving = ref(false)

function startAdding(adjustmentType: ConstructionAccountManualAdjustmentType) {
  draft.value = { id: null, adjustment_type: adjustmentType, amount: '', date: todayISO(), note: '' }
}

function startEditing(adjustment: ConstructionAccountManualAdjustment) {
  draft.value = { id: adjustment.id, adjustment_type: adjustment.adjustment_type, amount: String(adjustment.amount_dollars),
    date: adjustment.date, note: adjustment.note ?? '' }
}

function errorMessageOf(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : 'The entry could not be saved.'
}

async function saveDraft() {
  const current = draft.value
  const amount = Number(current?.amount)
  if (!current || !Number.isFinite(amount) || amount <= 0 || !current.date) return
  isSaving.value = true
  try {
    const data = { adjustment_type: current.adjustment_type, amount_dollars: Math.round(amount * 100) / 100, date: current.date, note: current.note.trim() || null }
    const saved = current.id
      ? await store.updateManualAdjustment(props.boughtDealId, current.id, data)
      : await store.addManualAdjustment(props.boughtDealId, data)
    if (saved) draft.value = null
  } catch (error) {
    emit('error', errorMessageOf(error))
  } finally {
    isSaving.value = false
  }
}

async function remove(adjustment: ConstructionAccountManualAdjustment) {
  try {
    await store.deleteManualAdjustment(props.boughtDealId, adjustment.id)
  } catch (error) {
    emit('error', errorMessageOf(error))
  }
}
</script>

<template>
  <div :data-testid="`ca.${boughtDealId}.manual-entries`" class="space-y-2">
    <p v-if="!adjustments.length && !draft" class="text-xs text-fg-muted">
      Nothing entered by hand. Add a payment you made from another account, by card or in cash, or a draw the lender wired somewhere else.
    </p>
    <ul v-if="adjustments.length" class="divide-y divide-line rounded-ctl border border-line">
      <li v-for="adjustment in adjustments" :key="adjustment.id" :data-testid="`ca.${boughtDealId}.manual-entry.${adjustment.id}`"
          class="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm">
        <span class="min-w-0">
          <span class="text-fg">{{ TYPE_LABELS[adjustment.adjustment_type] }}</span>
          <span class="ml-2 text-xs text-fg-muted">{{ adjustment.date }}<template v-if="adjustment.note"> · {{ adjustment.note }}</template></span>
        </span>
        <span class="flex items-center gap-1">
          <span class="numeric font-semibold">{{ formatMoney(adjustment.amount_dollars) }}</span>
          <UiIconButton :data-testid="`ca.${boughtDealId}.manual-entry.${adjustment.id}.edit`" label="Edit this entry" @click="startEditing(adjustment)">
            <i class="pi pi-pencil text-xs" aria-hidden="true"></i>
          </UiIconButton>
          <UiIconButton :data-testid="`ca.${boughtDealId}.manual-entry.${adjustment.id}.delete`" label="Delete this entry" variant="danger" @click="remove(adjustment)">
            <i class="pi pi-trash text-xs" aria-hidden="true"></i>
          </UiIconButton>
        </span>
      </li>
    </ul>

    <form v-if="draft" :data-testid="`ca.${boughtDealId}.manual-entry-form`" class="grid grid-cols-1 gap-2 rounded-ctl border border-line p-3 sm:grid-cols-2" @submit.prevent="saveDraft">
      <label class="flex flex-col gap-1 text-xs text-fg-muted sm:col-span-2">Kind
        <select v-model="draft.adjustment_type" :data-testid="`ca.${boughtDealId}.manual-entry-form.type`" class="ui-input text-sm">
          <option value="manual_payment">{{ TYPE_LABELS.manual_payment }}</option>
          <option value="manual_draw">{{ TYPE_LABELS.manual_draw }}</option>
        </select>
      </label>
      <label class="flex flex-col gap-1 text-xs text-fg-muted">Amount ($)
        <input v-model="draft.amount" :data-testid="`ca.${boughtDealId}.manual-entry-form.amount`" type="number" min="0.01" step="0.01" inputmode="decimal" required class="ui-input numeric text-sm" />
      </label>
      <label class="flex flex-col gap-1 text-xs text-fg-muted">Date
        <input v-model="draft.date" :data-testid="`ca.${boughtDealId}.manual-entry-form.date`" type="date" required class="ui-input text-sm" />
      </label>
      <label class="flex flex-col gap-1 text-xs text-fg-muted sm:col-span-2">Note (optional)
        <input v-model="draft.note" :data-testid="`ca.${boughtDealId}.manual-entry-form.note`" type="text" maxlength="500" class="ui-input text-sm" placeholder="Tile on the credit card" />
      </label>
      <div class="flex justify-end gap-2 sm:col-span-2">
        <UiButton variant="ghost" size="sm" :data-testid="`ca.${boughtDealId}.manual-entry-form.cancel`" @click="draft = null">Cancel</UiButton>
        <UiButton type="submit" size="sm" :data-testid="`ca.${boughtDealId}.manual-entry-form.save`" :loading="isSaving">Save</UiButton>
      </div>
    </form>
    <div v-else class="flex flex-wrap gap-2">
      <UiButton variant="secondary" size="sm" :data-testid="`ca.${boughtDealId}.add-manual-payment`" @click="startAdding('manual_payment')">
        <i class="pi pi-plus mr-1.5 text-xs" aria-hidden="true"></i>Payment made elsewhere
      </UiButton>
      <UiButton variant="secondary" size="sm" :data-testid="`ca.${boughtDealId}.add-manual-draw`" @click="startAdding('manual_draw')">
        <i class="pi pi-plus mr-1.5 text-xs" aria-hidden="true"></i>Draw received elsewhere
      </UiButton>
    </div>
  </div>
</template>
