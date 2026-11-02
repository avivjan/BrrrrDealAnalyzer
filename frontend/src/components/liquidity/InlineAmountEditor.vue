<script setup lang="ts">
/**
 * A row's amount you tap to edit in place: the signed amount reads as a button; tapping it
 * opens a dollar box seeded with the amount (sign kept: money out stays money out). Enter or
 * leaving the box saves, Escape cancels. A recurring occurrence is read-only here.
 */
import { nextTick, ref } from 'vue'

import type { LiquidityTransaction } from '../../types/liquidity'
import { formatSignedMoney } from '../../utils/money'

const props = defineProps<{ txn: LiquidityTransaction }>()

const emit = defineEmits<{ (e: 'changeAmount', id: string, newAmountDollars: number): void }>()

const isEditing = ref(false)
const typedDollars = ref('')
const box = ref<HTMLInputElement | null>(null)

async function startEditing() {
  typedDollars.value = String(Math.abs(props.txn.amount_dollars))
  isEditing.value = true
  await nextTick()
  box.value?.select()
}

function save() {
  if (!isEditing.value) return
  isEditing.value = false
  const typed = Number(typedDollars.value)
  if (!Number.isFinite(typed) || typed <= 0) return
  const newAmountDollars = Math.round(typed * 100) / 100 * Math.sign(props.txn.amount_dollars || -1)
  if (newAmountDollars !== props.txn.amount_dollars) emit('changeAmount', props.txn.id, newAmountDollars)
}
</script>

<template>
  <span v-if="txn.recurring_rule_id" class="numeric">{{ formatSignedMoney(txn.amount_dollars) }}</span>
  <input
    v-else-if="isEditing"
    ref="box"
    v-model="typedDollars"
    :data-testid="`amount.${txn.id}.input`"
    :aria-label="`Amount of ${txn.description}, in dollars`"
    type="number"
    inputmode="decimal"
    min="0"
    step="0.01"
    class="ui-input numeric h-8 w-28 touch:h-11 text-right text-xs"
    @keydown.enter.prevent="save"
    @keydown.escape.prevent="isEditing = false"
    @blur="save"
  />
  <button
    v-else
    type="button"
    :data-testid="`amount.${txn.id}`"
    class="numeric rounded-ctl px-1 underline decoration-dotted underline-offset-2 hover:bg-surface-3"
    :title="'Tap to change the amount'"
    @click="startEditing"
  >
    {{ formatSignedMoney(txn.amount_dollars) }}
  </button>
</template>
