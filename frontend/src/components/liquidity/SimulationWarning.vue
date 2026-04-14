<script setup lang="ts">
import type { SimulationResult } from '../../types/liquidity'

const props = defineProps<{
  open: boolean
  result: SimulationResult | null
  severity: 'hard' | 'soft' | 'none'
}>()

const emit = defineEmits<{
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()

function formatDate(iso: string): string {
  const [y, m, d] = iso.split('-')
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  return months[parseInt(m) - 1] + ' ' + parseInt(d) + ', ' + y
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="open && result"
        class="fixed inset-0 z-[60] flex items-center justify-center"
      >
        <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" @click="$emit('cancel')" />
        <div class="relative bg-[#141722] border rounded-xl shadow-2xl w-full max-w-lg mx-4 p-6"
          :class="severity === 'hard' ? 'border-red-500/50' : 'border-amber-500/40'"
        >
          <!-- Hard negative -->
          <template v-if="severity === 'hard'">
            <div class="flex items-center gap-3 mb-4">
              <div class="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center shrink-0">
                <i class="pi pi-exclamation-triangle text-red-400 text-xl"></i>
              </div>
              <div>
                <h3 class="text-lg font-bold text-red-300 font-mono">Balance Goes Negative</h3>
                <p class="text-xs text-slate-400 font-mono">This transaction would cause a negative balance on future dates.</p>
              </div>
            </div>

            <div class="bg-red-500/10 border border-red-500/20 rounded-lg p-3 mb-4 max-h-40 overflow-y-auto">
              <p class="text-xs text-red-300 font-mono font-semibold mb-2">
                Negative on {{ result.negativeDates.length }} date{{ result.negativeDates.length > 1 ? 's' : '' }}:
              </p>
              <div class="space-y-0.5">
                <div
                  v-for="date in result.negativeDates.slice(0, 10)"
                  :key="date"
                  class="text-[11px] text-red-400/80 font-mono"
                >
                  {{ formatDate(date) }}
                </div>
                <div v-if="result.negativeDates.length > 10" class="text-[11px] text-red-400/60 font-mono">
                  + {{ result.negativeDates.length - 10 }} more dates
                </div>
              </div>
            </div>

            <div class="bg-[#1e2030] rounded-lg p-3 mb-5 font-mono text-xs text-slate-300 space-y-1">
              <div>Window minimum: <span class="text-red-400 font-bold">{{ result.min.toFixed(2) }}k</span></div>
              <div>First negative: <span class="text-red-400">{{ result.firstNegativeDate ? formatDate(result.firstNegativeDate) : '—' }}</span></div>
              <div>Min reached on: <span class="text-slate-200">{{ result.minDates.slice(0, 3).map(formatDate).join(', ') }}{{ result.minDates.length > 3 ? ' +more' : '' }}</span></div>
            </div>

            <div class="flex gap-3 justify-end">
              <button
                class="px-4 py-2 text-sm font-mono text-slate-400 hover:text-slate-200 transition-colors"
                @click="$emit('cancel')"
              >
                Cancel
              </button>
              <button
                class="px-5 py-2 rounded-lg text-sm font-mono font-semibold bg-red-500/20 text-red-300 hover:bg-red-500/30 border border-red-500/30 transition-all"
                @click="$emit('confirm')"
              >
                Add Anyway
              </button>
            </div>
          </template>

          <!-- Soft warning (reserve breach) -->
          <template v-else-if="severity === 'soft'">
            <div class="flex items-center gap-3 mb-4">
              <div class="w-10 h-10 rounded-full bg-amber-500/20 flex items-center justify-center shrink-0">
                <i class="pi pi-info-circle text-amber-400 text-xl"></i>
              </div>
              <div>
                <h3 class="text-lg font-bold text-amber-300 font-mono">Below Reserve Threshold</h3>
                <p class="text-xs text-slate-400 font-mono">Balance will drop below your configured reserve on some dates.</p>
              </div>
            </div>

            <div class="bg-[#1e2030] rounded-lg p-3 mb-5 font-mono text-xs text-slate-300 space-y-1">
              <div>Window minimum: <span class="text-amber-400 font-bold">{{ result.min.toFixed(2) }}k</span></div>
              <div>Min reached on: <span class="text-slate-200">{{ result.minDates.slice(0, 3).map(formatDate).join(', ') }}</span></div>
              <div>Dates below reserve: <span class="text-amber-400">{{ result.reserveBreachDates.length }}</span></div>
            </div>

            <div class="flex gap-3 justify-end">
              <button
                class="px-4 py-2 text-sm font-mono text-slate-400 hover:text-slate-200 transition-colors"
                @click="$emit('cancel')"
              >
                Cancel
              </button>
              <button
                class="px-5 py-2 rounded-lg text-sm font-mono font-semibold bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-500/30 transition-all"
                @click="$emit('confirm')"
              >
                Save Anyway
              </button>
            </div>
          </template>
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
</style>
