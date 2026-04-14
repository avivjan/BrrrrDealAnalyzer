<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { LiquidityTransaction } from '../../types/liquidity'
import { todayISO } from '../../utils/liquidityEngine'

const props = defineProps<{
  open: boolean
  editTxn?: LiquidityTransaction | null
  prefillDate?: string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', data: { effective_date: string; description: string; amount_k: number; id?: string }): void
}>()

const isOutflow = ref(true)
const amount = ref('')
const description = ref('')
const effectiveDate = ref(todayISO())

const isEditing = computed(() => !!props.editTxn)
const title = computed(() => isEditing.value ? 'Edit Transaction' : 'Add Transaction')

watch(() => props.open, (open) => {
  if (!open) return
  if (props.editTxn) {
    isOutflow.value = props.editTxn.amount_k < 0
    amount.value = Math.abs(props.editTxn.amount_k).toString()
    description.value = props.editTxn.description
    effectiveDate.value = props.editTxn.effective_date
  } else {
    isOutflow.value = true
    amount.value = ''
    description.value = ''
    effectiveDate.value = props.prefillDate || todayISO()
  }
})

const isValid = computed(() => {
  const a = parseFloat(amount.value)
  return a > 0 && description.value.trim().length > 0 && effectiveDate.value.length > 0
})

function onSave() {
  if (!isValid.value) return
  const a = parseFloat(amount.value)
  const signedAmount = isOutflow.value ? -Math.abs(a) : Math.abs(a)
  emit('save', {
    effective_date: effectiveDate.value,
    description: description.value.trim(),
    amount_k: signedAmount,
    id: props.editTxn?.id,
  })
}

function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
  if (e.key === 'Enter' && e.metaKey && isValid.value) onSave()
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex items-center justify-center"
        @keydown="onKeyDown"
      >
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="$emit('close')" />
        <div class="relative bg-[#141722] border border-[#2a2f45] rounded-xl shadow-2xl w-full max-w-md mx-4 p-6">
          <h2 class="text-lg font-bold text-slate-100 mb-5 font-mono">{{ title }}</h2>

          <!-- Direction toggle -->
          <div class="flex gap-2 mb-4">
            <button
              class="flex-1 py-2 rounded-lg text-sm font-mono font-semibold transition-all"
              :class="!isOutflow ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' : 'bg-[#1e2030] text-slate-500 border border-transparent hover:border-slate-600'"
              @click="isOutflow = false"
            >
              + Inflow
            </button>
            <button
              class="flex-1 py-2 rounded-lg text-sm font-mono font-semibold transition-all"
              :class="isOutflow ? 'bg-red-500/20 text-red-400 border border-red-500/40' : 'bg-[#1e2030] text-slate-500 border border-transparent hover:border-slate-600'"
              @click="isOutflow = true"
            >
              − Outflow
            </button>
          </div>

          <!-- Amount -->
          <div class="mb-4">
            <label class="block text-xs text-slate-400 mb-1 font-mono">Amount ($k)</label>
            <div class="relative">
              <input
                v-model="amount"
                type="number"
                step="0.01"
                min="0"
                placeholder="49.2"
                class="w-full bg-[#1e2030] border border-[#2a2f45] rounded-lg px-3 py-2.5 text-slate-100 font-mono text-lg placeholder-slate-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30"
              />
              <span class="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-500 font-mono">k</span>
            </div>
            <p class="text-[10px] text-slate-500 mt-1 font-mono">All amounts in $k. e.g. 49.2 = $49,200</p>
          </div>

          <!-- Date -->
          <div class="mb-4">
            <label class="block text-xs text-slate-400 mb-1 font-mono">Date</label>
            <input
              v-model="effectiveDate"
              type="date"
              class="w-full bg-[#1e2030] border border-[#2a2f45] rounded-lg px-3 py-2.5 text-slate-100 font-mono focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 [color-scheme:dark]"
            />
          </div>

          <!-- Description -->
          <div class="mb-6">
            <label class="block text-xs text-slate-400 mb-1 font-mono">Description</label>
            <input
              v-model="description"
              type="text"
              placeholder="Rehab draw #2, 123 Main St"
              maxlength="500"
              class="w-full bg-[#1e2030] border border-[#2a2f45] rounded-lg px-3 py-2.5 text-slate-100 font-mono placeholder-slate-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30"
            />
          </div>

          <!-- Actions -->
          <div class="flex gap-3 justify-end">
            <button
              class="px-4 py-2 text-sm font-mono text-slate-400 hover:text-slate-200 transition-colors"
              @click="$emit('close')"
            >
              Cancel
            </button>
            <button
              :disabled="!isValid"
              class="px-5 py-2 rounded-lg text-sm font-mono font-semibold transition-all disabled:opacity-30 disabled:cursor-not-allowed"
              :class="isOutflow
                ? 'bg-red-500/20 text-red-300 hover:bg-red-500/30 border border-red-500/30'
                : 'bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 border border-emerald-500/30'"
              @click="onSave"
            >
              {{ isEditing ? 'Update' : 'Add' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active, .modal-leave-active {
  transition: all 0.2s ease;
}
.modal-enter-from, .modal-leave-to {
  opacity: 0;
}
.modal-enter-from .relative, .modal-leave-to .relative {
  transform: scale(0.95);
}
</style>
