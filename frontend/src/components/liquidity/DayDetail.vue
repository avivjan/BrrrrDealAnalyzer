<script setup lang="ts">
import type { DayBucket } from '../../types/liquidity'

defineProps<{
  bucket: DayBucket | null
}>()

defineEmits<{
  (e: 'editTxn', id: string): void
  (e: 'deleteTxn', id: string): void
  (e: 'addOnDate', date: string): void
}>()

function formatDate(iso: string): string {
  const parts = iso.split('-')
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  return (months[parseInt(parts[1] ?? '0') - 1] ?? '') + ' ' + parseInt(parts[2] ?? '0') + ', ' + (parts[0] ?? '')
}
</script>

<template>
  <div v-if="bucket" data-testid="daydetail.root" class="rounded-card border border-line bg-surface p-4 shadow-1">
    <div class="mb-3 flex items-center justify-between gap-2">
      <h3 class="min-w-0 truncate text-sm font-semibold text-fg">{{ formatDate(bucket.date) }}</h3>
      <UiButton
        data-testid="daydetail.add"
        variant="ghost"
        size="sm"
        class="min-h-9 touch:min-h-11 shrink-0 text-primary hover:text-primary-hover"
        @click="$emit('addOnDate', bucket.date)"
      >
        + Add flow
      </UiButton>
    </div>

    <div class="mb-3 flex gap-4 text-xs">
      <div>
        <span class="text-fg-muted">Net: </span>
        <span class="tabular font-semibold" :class="bucket.net_k > 0 ? 'text-positive' : bucket.net_k < 0 ? 'text-negative' : 'text-fg-muted'">
          {{ bucket.net_k > 0 ? '+' : '' }}{{ bucket.net_k.toFixed(2) }}k
        </span>
      </div>
      <div>
        <span class="text-fg-muted">EOD: </span>
        <span :class="bucket.balance_k < 0 ? 'text-negative' : 'text-primary'" class="tabular font-bold">
          {{ bucket.balance_k.toFixed(2) }}k
        </span>
      </div>
    </div>

    <div v-if="bucket.transactions.length === 0" data-testid="daydetail.empty" class="py-2 text-xs text-fg-muted">
      No transactions on this date.
    </div>

    <div v-else class="space-y-1.5">
      <div
        v-for="txn in bucket.transactions"
        :key="txn.id"
        :data-testid="`daydetail.txn.${txn.id}`"
        class="group flex items-center gap-2 rounded-ctl bg-surface-muted px-3 py-2"
        :class="txn.recurring_rule_id ? 'ring-1 ring-inset ring-primary/30' : ''"
      >
        <div class="h-1.5 w-1.5 shrink-0 rounded-full"
          :class="txn.amount_k > 0 ? 'bg-positive' : 'bg-negative'"
        />
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-1.5">
            <div class="min-w-0 break-words text-xs text-fg line-clamp-2">{{ txn.description }}</div>
            <UiBadge
              v-if="txn.recurring_rule_id"
              tone="primary"
              class="shrink-0 gap-0.5 px-1 py-0.5 text-[9px]"
              title="Projected from a recurring rule. Edit/delete affects the whole series."
            >
              <i class="pi pi-refresh text-[8px]" aria-hidden="true"></i>
              recurring
            </UiBadge>
          </div>
        </div>
        <div class="shrink-0 text-xs font-bold tabular"
          :class="txn.amount_k > 0 ? 'text-positive' : 'text-negative'"
        >
          {{ txn.amount_k > 0 ? '+' : '' }}{{ txn.amount_k.toFixed(2) }}k
        </div>
        <div class="flex shrink-0 gap-2 opacity-0 transition-opacity duration-fast ease-standard focus-within:opacity-100 group-hover:opacity-100 touch:opacity-100">
          <UiIconButton
            :data-testid="`daydetail.txn.${txn.id}.edit`"
            :title="txn.recurring_rule_id ? 'Edit recurring series' : 'Edit'"
            :label="txn.recurring_rule_id ? 'Edit recurring series' : 'Edit'"
            @click="$emit('editTxn', txn.id)"
          >
            <i class="pi pi-pencil text-[10px]" aria-hidden="true"></i>
          </UiIconButton>
          <UiIconButton
            :data-testid="`daydetail.txn.${txn.id}.delete`"
            variant="danger"
            :title="txn.recurring_rule_id ? 'Delete recurring series' : 'Delete'"
            :label="txn.recurring_rule_id ? 'Delete recurring series' : 'Delete'"
            @click="$emit('deleteTxn', txn.id)"
          >
            <i class="pi pi-trash text-[10px]" aria-hidden="true"></i>
          </UiIconButton>
        </div>
      </div>
    </div>
  </div>
</template>
