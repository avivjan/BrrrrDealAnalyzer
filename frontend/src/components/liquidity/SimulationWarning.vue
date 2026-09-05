<script setup lang="ts">
import type { SimulationResult } from '../../types/liquidity'

defineProps<{
  open: boolean
  result: SimulationResult | null
  severity: 'hard' | 'soft' | 'none'
}>()

defineEmits<{
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()

function formatDate(iso: string): string {
  const parts = iso.split('-')
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  return (months[parseInt(parts[1] ?? '0') - 1] ?? '') + ' ' + parseInt(parts[2] ?? '0') + ', ' + (parts[0] ?? '')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="open && result"
        data-testid="simwarn.root"
        class="fixed inset-0 z-[60] flex items-center justify-center p-4"
      >
        <div data-testid="simwarn.backdrop" class="absolute inset-0 bg-fg/60 md:backdrop-blur-sm" @click="$emit('cancel')" />
        <UiModalPanel
          size="md"
          labelled-by="simwarn-modal-title"
          class="modal-panel relative border"
          :class="severity === 'hard' ? 'border-negative/50' : 'border-warning/50'"
        >
          <!-- Hard negative -->
          <template v-if="severity === 'hard'">
            <div class="mb-4 flex items-center gap-3">
              <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-negative/10">
                <i class="pi pi-exclamation-triangle text-xl text-negative" aria-hidden="true"></i>
              </div>
              <div class="min-w-0">
                <h3 id="simwarn-modal-title" class="text-lg font-bold text-negative">Balance Goes Negative</h3>
                <p class="text-xs text-fg-muted">This transaction would cause a negative balance on future dates.</p>
              </div>
            </div>

            <div class="mb-4 max-h-40 overflow-y-auto overscroll-contain rounded-card border border-negative/20 bg-negative/5 p-3">
              <p class="mb-2 text-xs font-semibold text-negative">
                Negative on {{ result.negativeDates.length }} date{{ result.negativeDates.length > 1 ? 's' : '' }}:
              </p>
              <div class="space-y-0.5">
                <div
                  v-for="date in result.negativeDates.slice(0, 10)"
                  :key="date"
                  :data-testid="`simwarn.negative-date.${date}`"
                  class="text-[11px] tabular text-negative"
                >
                  {{ formatDate(date) }}
                </div>
                <div v-if="result.negativeDates.length > 10" class="text-[11px] text-fg-muted">
                  + {{ result.negativeDates.length - 10 }} more dates
                </div>
              </div>
            </div>

            <div class="mb-5 space-y-1 rounded-card bg-surface-muted p-3 text-xs text-fg">
              <div>Window minimum: <span class="font-bold tabular text-negative">{{ result.min.toFixed(2) }}k</span></div>
              <div>First negative: <span class="tabular text-negative">{{ result.firstNegativeDate ? formatDate(result.firstNegativeDate) : '—' }}</span></div>
              <div>Min reached on: <span class="tabular text-fg">{{ result.minDates.slice(0, 3).map(formatDate).join(', ') }}{{ result.minDates.length > 3 ? ' +more' : '' }}</span></div>
            </div>

            <div class="flex flex-wrap justify-end gap-3">
              <UiButton
                data-testid="simwarn.cancel"
                variant="ghost"
                @click="$emit('cancel')"
              >
                Cancel
              </UiButton>
              <UiButton
                data-testid="simwarn.confirm"
                variant="danger"
                @click="$emit('confirm')"
              >
                Add Anyway
              </UiButton>
            </div>
          </template>

          <!-- Soft warning (reserve breach) -->
          <template v-else-if="severity === 'soft'">
            <div class="mb-4 flex items-center gap-3">
              <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-warning/10">
                <i class="pi pi-info-circle text-xl text-warning" aria-hidden="true"></i>
              </div>
              <div class="min-w-0">
                <h3 id="simwarn-modal-title" class="text-lg font-bold text-warning">Below Reserve Threshold</h3>
                <p class="text-xs text-fg-muted">Balance will drop below your configured reserve on some dates.</p>
              </div>
            </div>

            <div class="mb-5 space-y-1 rounded-card bg-surface-muted p-3 text-xs text-fg">
              <div>Window minimum: <span class="font-bold tabular text-warning">{{ result.min.toFixed(2) }}k</span></div>
              <div>Min reached on: <span class="tabular text-fg">{{ result.minDates.slice(0, 3).map(formatDate).join(', ') }}</span></div>
              <div>Dates below reserve: <span class="tabular text-warning">{{ result.reserveBreachDates.length }}</span></div>
            </div>

            <div class="flex flex-wrap justify-end gap-3">
              <UiButton
                data-testid="simwarn.cancel"
                variant="ghost"
                @click="$emit('cancel')"
              >
                Cancel
              </UiButton>
              <UiButton
                data-testid="simwarn.confirm"
                variant="primary"
                class="bg-warning hover:bg-warning/90"
                @click="$emit('confirm')"
              >
                Save Anyway
              </UiButton>
            </div>
          </template>
        </UiModalPanel>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active, .modal-leave-active {
  transition: opacity var(--dur-fast) var(--ease-standard);
}
.modal-enter-from, .modal-leave-to {
  opacity: 0;
}
.modal-enter-active .modal-panel, .modal-leave-active .modal-panel {
  transition: transform var(--dur-fast) var(--ease-standard);
}
.modal-enter-from .modal-panel, .modal-leave-to .modal-panel { transform: scale(0.97); }
</style>
