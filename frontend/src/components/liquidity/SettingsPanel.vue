<script setup lang="ts">
import { ref, watch } from 'vue'
import type { LiquiditySettings } from '../../types/liquidity'

const props = defineProps<{
  open: boolean
  settings: LiquiditySettings
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', data: { opening_balance_k: number; opening_balance_date: string; reserve_k: number }): void
}>()

const balanceK = ref('')
const balanceDate = ref('')
const reserveK = ref('')

watch(() => props.open, (open) => {
  if (!open) return
  balanceK.value = props.settings.opening_balance_k.toString()
  balanceDate.value = props.settings.opening_balance_date
  reserveK.value = props.settings.reserve_k.toString()
})

function onSave() {
  const b = parseFloat(balanceK.value)
  const r = parseFloat(reserveK.value)
  if (isNaN(b) || !balanceDate.value) return
  emit('save', {
    opening_balance_k: b,
    opening_balance_date: balanceDate.value,
    reserve_k: isNaN(r) ? 5 : r,
  })
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="$emit('close')" />
        <div class="relative bg-[#141722] border border-[#2a2f45] rounded-xl shadow-2xl w-full max-w-md mx-4 p-6">
          <h2 class="text-lg font-bold text-slate-100 mb-5 font-mono">Liquidity Settings</h2>

          <div class="mb-4">
            <label class="block text-xs text-slate-400 mb-1 font-mono">Opening Balance ($k)</label>
            <div class="relative">
              <input
                v-model="balanceK"
                type="number"
                step="0.01"
                class="w-full bg-[#1e2030] border border-[#2a2f45] rounded-lg px-3 py-2.5 text-slate-100 font-mono text-lg placeholder-slate-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30"
              />
              <span class="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-500 font-mono">k</span>
            </div>
            <p class="text-[10px] text-slate-500 mt-1 font-mono">Balance at start of the anchor date. e.g. 49 = $49,000</p>
          </div>

          <div class="mb-4">
            <label class="block text-xs text-slate-400 mb-1 font-mono">As-of Date</label>
            <input
              v-model="balanceDate"
              type="date"
              class="w-full bg-[#1e2030] border border-[#2a2f45] rounded-lg px-3 py-2.5 text-slate-100 font-mono focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 [color-scheme:dark]"
            />
          </div>

          <div class="mb-6">
            <label class="block text-xs text-slate-400 mb-1 font-mono">Reserve Threshold ($k)</label>
            <div class="relative">
              <input
                v-model="reserveK"
                type="number"
                step="0.1"
                min="0"
                class="w-full bg-[#1e2030] border border-[#2a2f45] rounded-lg px-3 py-2.5 text-slate-100 font-mono placeholder-slate-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30"
              />
              <span class="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-500 font-mono">k</span>
            </div>
            <p class="text-[10px] text-slate-500 mt-1 font-mono">Soft warning if balance drops below this. Default: 5k</p>
          </div>

          <div class="flex gap-3 justify-end">
            <button
              class="px-4 py-2 text-sm font-mono text-slate-400 hover:text-slate-200 transition-colors"
              @click="$emit('close')"
            >
              Cancel
            </button>
            <button
              class="px-5 py-2 rounded-lg text-sm font-mono font-semibold bg-indigo-500/20 text-indigo-300 hover:bg-indigo-500/30 border border-indigo-500/30 transition-all"
              @click="onSave"
            >
              Save
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active, .modal-leave-active { transition: all 0.2s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
