<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type {
  LiquidityTransaction,
  LiquidityRecurringTransaction,
  LiquidityRecurringFrequency,
} from '../../types/liquidity'
import {
  addDays,
  describeRecurrence,
  expandRecurringRule,
  todayISO,
} from '../../utils/liquidityEngine'

/**
 * Unified add/edit modal for both one-off and recurring cash flows.
 *
 * The component owns no persistence — it emits a discriminated `save`
 * payload (`kind: 'transaction' | 'recurring'`) plus an optional `id` and
 * the parent decides which store action to call. This keeps the form
 * trivial to test and lets the parent run pre-save simulation warnings.
 */

const props = defineProps<{
  open: boolean
  editTxn?: LiquidityTransaction | null
  /** Pass the source rule when editing a virtual recurring instance. */
  editRecurring?: LiquidityRecurringTransaction | null
  prefillDate?: string | null
}>()

type SaveOneOff = {
  kind: 'transaction'
  id?: string
  effective_date: string
  description: string
  amount_k: number
}

type SaveRecurring = {
  kind: 'recurring'
  id?: string
  description: string
  amount_k: number
  start_date: string
  end_date: string | null
  occurrences: number | null
  frequency: LiquidityRecurringFrequency
  interval: number
}

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', data: SaveOneOff | SaveRecurring): void
}>()

const FREQUENCIES: { value: LiquidityRecurringFrequency; label: string }[] = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'biweekly', label: 'Biweekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'quarterly', label: 'Quarterly' },
  { value: 'yearly', label: 'Yearly' },
]

type EndMode = 'never' | 'on' | 'after'

// ---- form state ------------------------------------------------------------
const isOutflow = ref(true)
const amount = ref('')
const description = ref('')
const effectiveDate = ref(todayISO())

const isRecurring = ref(false)
const startDate = ref(todayISO())
const frequency = ref<LiquidityRecurringFrequency>('monthly')
const interval = ref('1')
const endMode = ref<EndMode>('never')
const endDate = ref(addDays(todayISO(), 365))
const occurrences = ref('12')

// ---- computed --------------------------------------------------------------
const isEditingOneOff = computed(() => !!props.editTxn && !props.editRecurring)
const isEditingRecurring = computed(() => !!props.editRecurring)
const isEditing = computed(() => isEditingOneOff.value || isEditingRecurring.value)

const title = computed(() => {
  if (isEditingRecurring.value) return 'Edit Recurring Flow'
  if (isEditingOneOff.value) return 'Edit Transaction'
  return isRecurring.value ? 'Add Recurring Flow' : 'Add Transaction'
})

// We hide the recurring toggle when editing an existing row to keep the
// "change one-off into recurring" edge case out of v1.
const canToggleRecurring = computed(() => !isEditing.value)

watch(() => props.open, (open) => {
  if (!open) return

  if (props.editRecurring) {
    const r = props.editRecurring
    isRecurring.value = true
    isOutflow.value = r.amount_k < 0
    amount.value = Math.abs(r.amount_k).toString()
    description.value = r.description
    startDate.value = r.start_date
    frequency.value = r.frequency
    interval.value = String(r.interval || 1)
    if (r.occurrences != null) {
      endMode.value = 'after'
      occurrences.value = String(r.occurrences)
    } else if (r.end_date) {
      endMode.value = 'on'
      endDate.value = r.end_date
    } else {
      endMode.value = 'never'
    }
  } else if (props.editTxn) {
    isRecurring.value = false
    isOutflow.value = props.editTxn.amount_k < 0
    amount.value = Math.abs(props.editTxn.amount_k).toString()
    description.value = props.editTxn.description
    effectiveDate.value = props.editTxn.effective_date
  } else {
    isRecurring.value = false
    isOutflow.value = true
    amount.value = ''
    description.value = ''
    effectiveDate.value = props.prefillDate || todayISO()
    startDate.value = props.prefillDate || todayISO()
    frequency.value = 'monthly'
    interval.value = '1'
    endMode.value = 'never'
    endDate.value = addDays(props.prefillDate || todayISO(), 365)
    occurrences.value = '12'
  }
})

const intervalNum = computed(() => {
  const n = parseInt(interval.value, 10)
  return Number.isFinite(n) && n > 0 ? n : 1
})

const occurrencesNum = computed(() => {
  const n = parseInt(occurrences.value, 10)
  return Number.isFinite(n) && n > 0 ? n : null
})

const isValid = computed(() => {
  const a = parseFloat(amount.value)
  if (!(a > 0)) return false
  if (description.value.trim().length === 0) return false

  if (isRecurring.value) {
    if (!startDate.value) return false
    if (endMode.value === 'on' && (!endDate.value || endDate.value < startDate.value)) return false
    if (endMode.value === 'after' && !occurrencesNum.value) return false
    return true
  }

  return effectiveDate.value.length > 0
})

const recurrencePreview = computed(() => {
  if (!isRecurring.value || !isValid.value) return null
  const a = parseFloat(amount.value)
  const signedAmount = isOutflow.value ? -Math.abs(a) : Math.abs(a)
  const virtualRule: LiquidityRecurringTransaction = {
    id: '__preview__',
    description: description.value.trim() || 'Preview',
    amount_k: signedAmount,
    start_date: startDate.value,
    end_date: endMode.value === 'on' ? endDate.value : null,
    occurrences: endMode.value === 'after' ? occurrencesNum.value : null,
    frequency: frequency.value,
    interval: intervalNum.value,
  }
  // Project up to 5 occurrences inside a 5-year window for the preview.
  const previewWindowEnd = addDays(startDate.value, 365 * 5)
  const projected = expandRecurringRule(virtualRule, startDate.value, previewWindowEnd)
  const first5 = projected.slice(0, 5)
  return {
    cadence: describeRecurrence(virtualRule),
    upcoming: first5,
    totalShown: projected.length,
  }
})

function onSave() {
  if (!isValid.value) return
  const a = parseFloat(amount.value)
  const signedAmount = isOutflow.value ? -Math.abs(a) : Math.abs(a)

  if (isRecurring.value) {
    emit('save', {
      kind: 'recurring',
      id: props.editRecurring?.id,
      description: description.value.trim(),
      amount_k: signedAmount,
      start_date: startDate.value,
      end_date: endMode.value === 'on' ? endDate.value : null,
      occurrences: endMode.value === 'after' ? occurrencesNum.value : null,
      frequency: frequency.value,
      interval: intervalNum.value,
    })
    return
  }

  emit('save', {
    kind: 'transaction',
    id: props.editTxn?.id,
    effective_date: effectiveDate.value,
    description: description.value.trim(),
    amount_k: signedAmount,
  })
}

function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
  if (e.key === 'Enter' && e.metaKey && isValid.value) onSave()
}

function formatPreviewDate(iso: string): string {
  const parts = iso.split('-')
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  return (months[parseInt(parts[1] ?? '0') - 1] ?? '') + ' ' + parseInt(parts[2] ?? '0') + ', ' + (parts[0] ?? '')
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
        <div class="relative bg-[#141722] border border-[#2a2f45] rounded-xl shadow-2xl w-full max-w-md mx-4 p-6 max-h-[90vh] overflow-y-auto">
          <h2 class="text-lg font-bold text-slate-100 mb-5 font-mono flex items-center gap-2">
            <i v-if="isRecurring" class="pi pi-refresh text-indigo-400 text-sm"></i>
            {{ title }}
          </h2>

          <!-- Recurring toggle (only for new entries; editing locks the type) -->
          <div v-if="canToggleRecurring" class="flex gap-2 mb-4">
            <button
              class="flex-1 py-2 rounded-lg text-xs font-mono font-semibold transition-all flex items-center justify-center gap-1.5"
              :class="!isRecurring ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40' : 'bg-[#1e2030] text-slate-500 border border-transparent hover:border-slate-600'"
              @click="isRecurring = false"
            >
              <i class="pi pi-circle-fill text-[8px]"></i> One-time
            </button>
            <button
              class="flex-1 py-2 rounded-lg text-xs font-mono font-semibold transition-all flex items-center justify-center gap-1.5"
              :class="isRecurring ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40' : 'bg-[#1e2030] text-slate-500 border border-transparent hover:border-slate-600'"
              @click="isRecurring = true"
            >
              <i class="pi pi-refresh text-[10px]"></i> Recurring
            </button>
          </div>

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
            <label class="block text-xs text-slate-400 mb-1 font-mono">
              {{ isRecurring ? 'Amount per occurrence ($k)' : 'Amount ($k)' }}
            </label>
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

          <!-- One-off date -->
          <div v-if="!isRecurring" class="mb-4">
            <label class="block text-xs text-slate-400 mb-1 font-mono">Date</label>
            <input
              v-model="effectiveDate"
              type="date"
              class="w-full bg-[#1e2030] border border-[#2a2f45] rounded-lg px-3 py-2.5 text-slate-100 font-mono focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 [color-scheme:dark]"
            />
          </div>

          <!-- Recurring schedule -->
          <div v-else class="mb-4 space-y-3">
            <div>
              <label class="block text-xs text-slate-400 mb-1 font-mono">First occurrence</label>
              <input
                v-model="startDate"
                type="date"
                class="w-full bg-[#1e2030] border border-[#2a2f45] rounded-lg px-3 py-2.5 text-slate-100 font-mono focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 [color-scheme:dark]"
              />
            </div>

            <div class="grid grid-cols-3 gap-2">
              <div class="col-span-2">
                <label class="block text-xs text-slate-400 mb-1 font-mono">Frequency</label>
                <select
                  v-model="frequency"
                  class="w-full bg-[#1e2030] border border-[#2a2f45] rounded-lg px-3 py-2.5 text-slate-100 font-mono focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 [color-scheme:dark]"
                >
                  <option v-for="f in FREQUENCIES" :key="f.value" :value="f.value">{{ f.label }}</option>
                </select>
              </div>
              <div>
                <label class="block text-xs text-slate-400 mb-1 font-mono" title="Multiplier on the base frequency, e.g. interval=2 with Weekly = every 2 weeks">
                  Every
                </label>
                <input
                  v-model="interval"
                  type="number"
                  min="1"
                  max="365"
                  class="w-full bg-[#1e2030] border border-[#2a2f45] rounded-lg px-3 py-2.5 text-slate-100 font-mono focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30"
                />
              </div>
            </div>

            <div>
              <label class="block text-xs text-slate-400 mb-1 font-mono">Ends</label>
              <div class="flex gap-1.5 mb-2">
                <button
                  type="button"
                  class="flex-1 py-1.5 rounded-lg text-[11px] font-mono transition-all"
                  :class="endMode === 'never' ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40' : 'bg-[#1e2030] text-slate-500 border border-transparent hover:border-slate-600'"
                  @click="endMode = 'never'"
                >
                  Never
                </button>
                <button
                  type="button"
                  class="flex-1 py-1.5 rounded-lg text-[11px] font-mono transition-all"
                  :class="endMode === 'on' ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40' : 'bg-[#1e2030] text-slate-500 border border-transparent hover:border-slate-600'"
                  @click="endMode = 'on'"
                >
                  On date
                </button>
                <button
                  type="button"
                  class="flex-1 py-1.5 rounded-lg text-[11px] font-mono transition-all"
                  :class="endMode === 'after' ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40' : 'bg-[#1e2030] text-slate-500 border border-transparent hover:border-slate-600'"
                  @click="endMode = 'after'"
                >
                  After N
                </button>
              </div>

              <input
                v-if="endMode === 'on'"
                v-model="endDate"
                type="date"
                :min="startDate"
                class="w-full bg-[#1e2030] border border-[#2a2f45] rounded-lg px-3 py-2.5 text-slate-100 font-mono focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 [color-scheme:dark]"
              />
              <div v-else-if="endMode === 'after'" class="relative">
                <input
                  v-model="occurrences"
                  type="number"
                  min="1"
                  max="2000"
                  class="w-full bg-[#1e2030] border border-[#2a2f45] rounded-lg px-3 py-2.5 pr-24 text-slate-100 font-mono focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30"
                />
                <span class="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] text-slate-500 font-mono">occurrence(s)</span>
              </div>
              <p v-else class="text-[10px] text-slate-500 font-mono">
                Series runs indefinitely on the timeline horizon.
              </p>
            </div>

            <!-- Preview -->
            <div
              v-if="recurrencePreview"
              class="bg-[#1a1d2e] border border-[#2a2f45] rounded-lg p-3"
            >
              <div class="flex items-center justify-between mb-1.5">
                <div class="text-[10px] uppercase tracking-wider text-slate-500 font-mono">
                  Next {{ recurrencePreview.upcoming.length }} of {{ recurrencePreview.totalShown }}
                </div>
                <div class="text-[10px] font-mono text-indigo-400">
                  {{ recurrencePreview.cadence }}
                </div>
              </div>
              <div
                v-for="(p, idx) in recurrencePreview.upcoming"
                :key="idx"
                class="flex items-baseline justify-between text-[11px] font-mono"
              >
                <span class="text-slate-400">{{ formatPreviewDate(p.effective_date) }}</span>
                <span :class="p.amount_k > 0 ? 'text-emerald-400' : 'text-red-400'">
                  {{ p.amount_k > 0 ? '+' : '' }}{{ p.amount_k.toFixed(2) }}k
                </span>
              </div>
              <div
                v-if="recurrencePreview.totalShown > recurrencePreview.upcoming.length"
                class="text-[10px] text-slate-500 font-mono mt-1"
              >
                +{{ recurrencePreview.totalShown - recurrencePreview.upcoming.length }} more inside the timeline
              </div>
            </div>
          </div>

          <!-- Description -->
          <div class="mb-6">
            <label class="block text-xs text-slate-400 mb-1 font-mono">Description</label>
            <input
              v-model="description"
              type="text"
              :placeholder="isRecurring ? 'HM interest, 123 Main' : 'Rehab draw #2, 123 Main St'"
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
              {{ isEditing ? 'Update' : (isRecurring ? 'Create Series' : 'Add') }}
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
