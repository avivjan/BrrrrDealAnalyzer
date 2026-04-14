<script setup lang="ts">
import type { DayBucket } from '../../types/liquidity'

const props = defineProps<{
  bucket: DayBucket | null
}>()

const emit = defineEmits<{
  (e: 'editTxn', id: string): void
  (e: 'deleteTxn', id: string): void
  (e: 'addOnDate', date: string): void
}>()

function formatDate(iso: string): string {
  const [y, m, d] = iso.split('-')
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  return months[parseInt(m) - 1] + ' ' + parseInt(d) + ', ' + y
}
</script>

<template>
  <div v-if="bucket" class="bg-[#141722] border border-[#2a2f45] rounded-xl p-4">
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-sm font-mono font-bold text-slate-200">{{ formatDate(bucket.date) }}</h3>
      <button
        class="text-xs font-mono text-indigo-400 hover:text-indigo-300 transition-colors"
        @click="$emit('addOnDate', bucket.date)"
      >
        + Add flow
      </button>
    </div>

    <div class="flex gap-4 mb-3 text-xs font-mono">
      <div>
        <span class="text-slate-500">Net: </span>
        <span :class="bucket.net_k > 0 ? 'text-emerald-400' : bucket.net_k < 0 ? 'text-red-400' : 'text-slate-400'">
          {{ bucket.net_k > 0 ? '+' : '' }}{{ bucket.net_k.toFixed(2) }}k
        </span>
      </div>
      <div>
        <span class="text-slate-500">EOD: </span>
        <span :class="bucket.balance_k < 0 ? 'text-red-400' : 'text-indigo-300'" class="font-bold">
          {{ bucket.balance_k.toFixed(2) }}k
        </span>
      </div>
    </div>

    <div v-if="bucket.transactions.length === 0" class="text-xs text-slate-500 font-mono py-2">
      No transactions on this date.
    </div>

    <div v-else class="space-y-1.5">
      <div
        v-for="txn in bucket.transactions"
        :key="txn.id"
        class="flex items-center gap-2 bg-[#1a1d2e] rounded-lg px-3 py-2 group"
      >
        <div class="w-1.5 h-1.5 rounded-full shrink-0"
          :class="txn.amount_k > 0 ? 'bg-emerald-400' : 'bg-red-400'"
        />
        <div class="flex-1 min-w-0">
          <div class="text-xs font-mono text-slate-300 truncate">{{ txn.description }}</div>
        </div>
        <div class="text-xs font-mono font-bold shrink-0"
          :class="txn.amount_k > 0 ? 'text-emerald-400' : 'text-red-400'"
        >
          {{ txn.amount_k > 0 ? '+' : '' }}{{ txn.amount_k.toFixed(2) }}k
        </div>
        <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
          <button
            class="w-6 h-6 flex items-center justify-center rounded text-slate-500 hover:text-indigo-400 hover:bg-indigo-500/10 transition-all"
            title="Edit"
            @click="$emit('editTxn', txn.id)"
          >
            <i class="pi pi-pencil text-[10px]"></i>
          </button>
          <button
            class="w-6 h-6 flex items-center justify-center rounded text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
            title="Delete"
            @click="$emit('deleteTxn', txn.id)"
          >
            <i class="pi pi-trash text-[10px]"></i>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
