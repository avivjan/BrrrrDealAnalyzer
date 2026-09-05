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
        data-testid="txnform.root"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @keydown="onKeyDown"
      >
        <div data-testid="txnform.backdrop" class="absolute inset-0 bg-fg/50 md:backdrop-blur-sm" @click="$emit('close')" />
        <UiModalPanel size="sm" labelled-by="txnform-modal-title" class="modal-panel relative">
          <template #header>
            <h2 id="txnform-modal-title" class="flex items-center gap-2 text-base font-semibold text-fg">
              <i v-if="isRecurring" class="pi pi-refresh text-sm text-primary" aria-hidden="true"></i>
              {{ title }}
            </h2>
          </template>

          <!-- Recurring toggle (only for new entries; editing locks the type) -->
          <div v-if="canToggleRecurring" class="mb-4 flex gap-2">
            <UiButton
              data-testid="txnform.mode-onetime"
              variant="ghost"
              class="flex-1 gap-1.5 text-xs font-semibold"
              :aria-pressed="!isRecurring"
              :class="!isRecurring ? 'bg-primary/10 text-primary ring-1 ring-inset ring-primary/40' : 'bg-surface-muted text-fg-muted'"
              @click="isRecurring = false"
            >
              <i class="pi pi-circle-fill text-[8px]" aria-hidden="true"></i> One-time
            </UiButton>
            <UiButton
              data-testid="txnform.mode-recurring"
              variant="ghost"
              class="flex-1 gap-1.5 text-xs font-semibold"
              :aria-pressed="isRecurring"
              :class="isRecurring ? 'bg-primary/10 text-primary ring-1 ring-inset ring-primary/40' : 'bg-surface-muted text-fg-muted'"
              @click="isRecurring = true"
            >
              <i class="pi pi-refresh text-[10px]" aria-hidden="true"></i> Recurring
            </UiButton>
          </div>

          <!-- Direction toggle -->
          <div class="mb-4 flex gap-2">
            <UiButton
              data-testid="txnform.inflow"
              variant="ghost"
              class="flex-1 text-sm font-semibold"
              :aria-pressed="!isOutflow"
              :class="!isOutflow ? 'bg-positive/10 text-positive ring-1 ring-inset ring-positive/40' : 'bg-surface-muted text-fg-muted'"
              @click="isOutflow = false"
            >
              + Inflow
            </UiButton>
            <UiButton
              data-testid="txnform.outflow"
              variant="ghost"
              class="flex-1 text-sm font-semibold"
              :aria-pressed="isOutflow"
              :class="isOutflow ? 'bg-negative/10 text-negative ring-1 ring-inset ring-negative/40' : 'bg-surface-muted text-fg-muted'"
              @click="isOutflow = true"
            >
              − Outflow
            </UiButton>
          </div>

          <!-- Amount -->
          <UiField class="mb-4">
            <template #label>
              {{ isRecurring ? 'Amount per occurrence ($k)' : 'Amount ($k)' }}
            </template>
            <template #default="{ id, describedBy }">
              <div class="relative">
                <input
                  data-testid="txnform.amount"
                  v-model="amount"
                  :id="id"
                  :aria-describedby="describedBy"
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="49.2"
                  class="ui-input pr-8 text-lg tabular"
                />
                <span class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-fg-muted">k</span>
              </div>
            </template>
            <template #helper>All amounts in $k. e.g. 49.2 = $49,200</template>
          </UiField>

          <!-- One-off date -->
          <UiField v-if="!isRecurring" class="mb-4">
            <template #label>Date</template>
            <template #default="{ id, describedBy }">
              <input
                data-testid="txnform.date"
                v-model="effectiveDate"
                :id="id"
                :aria-describedby="describedBy"
                type="date"
                class="ui-input"
              />
            </template>
          </UiField>

          <!-- Recurring schedule -->
          <div v-else class="mb-4 space-y-3">
            <UiField>
              <template #label>First occurrence</template>
              <template #default="{ id, describedBy }">
                <input
                  data-testid="txnform.start-date"
                  v-model="startDate"
                  :id="id"
                  :aria-describedby="describedBy"
                  type="date"
                  class="ui-input"
                />
              </template>
            </UiField>

            <div class="grid grid-cols-3 gap-2">
              <UiField class="col-span-2">
                <template #label>Frequency</template>
                <template #default="{ id, describedBy }">
                  <select
                    data-testid="txnform.frequency"
                    v-model="frequency"
                    :id="id"
                    :aria-describedby="describedBy"
                    class="ui-select"
                  >
                    <option v-for="f in FREQUENCIES" :key="f.value" :value="f.value">{{ f.label }}</option>
                  </select>
                </template>
              </UiField>
              <UiField title="Multiplier on the base frequency, e.g. interval=2 with Weekly = every 2 weeks">
                <template #label>
                  Every
                </template>
                <template #default="{ id, describedBy }">
                  <input
                    data-testid="txnform.interval"
                    v-model="interval"
                    :id="id"
                    :aria-describedby="describedBy"
                    type="number"
                    min="1"
                    max="365"
                    class="ui-input tabular"
                  />
                </template>
              </UiField>
            </div>

            <div>
              <label class="mb-1 block text-sm font-medium text-fg">Ends</label>
              <div class="mb-2 flex gap-1.5">
                <UiButton
                  type="button"
                  data-testid="txnform.end-never"
                  variant="ghost"
                  size="sm"
                  class="min-h-9 flex-1 text-[11px]"
                  :aria-pressed="endMode === 'never'"
                  :class="endMode === 'never' ? 'bg-primary/10 text-primary ring-1 ring-inset ring-primary/40' : 'bg-surface-muted text-fg-muted'"
                  @click="endMode = 'never'"
                >
                  Never
                </UiButton>
                <UiButton
                  type="button"
                  data-testid="txnform.end-on"
                  variant="ghost"
                  size="sm"
                  class="min-h-9 flex-1 text-[11px]"
                  :aria-pressed="endMode === 'on'"
                  :class="endMode === 'on' ? 'bg-primary/10 text-primary ring-1 ring-inset ring-primary/40' : 'bg-surface-muted text-fg-muted'"
                  @click="endMode = 'on'"
                >
                  On date
                </UiButton>
                <UiButton
                  type="button"
                  data-testid="txnform.end-after"
                  variant="ghost"
                  size="sm"
                  class="min-h-9 flex-1 text-[11px]"
                  :aria-pressed="endMode === 'after'"
                  :class="endMode === 'after' ? 'bg-primary/10 text-primary ring-1 ring-inset ring-primary/40' : 'bg-surface-muted text-fg-muted'"
                  @click="endMode = 'after'"
                >
                  After N
                </UiButton>
              </div>

              <input
                v-if="endMode === 'on'"
                data-testid="txnform.end-date"
                v-model="endDate"
                type="date"
                :min="startDate"
                class="ui-input"
              />
              <div v-else-if="endMode === 'after'" class="relative">
                <input
                  data-testid="txnform.occurrences"
                  v-model="occurrences"
                  type="number"
                  min="1"
                  max="2000"
                  class="ui-input pr-24 tabular"
                />
                <span class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[10px] text-fg-muted">occurrence(s)</span>
              </div>
              <p v-else class="text-[10px] text-fg-muted">
                Series runs indefinitely on the timeline horizon.
              </p>
            </div>

            <!-- Preview -->
            <div
              v-if="recurrencePreview"
              class="rounded-card border border-line bg-surface-muted p-3"
            >
              <div class="mb-1.5 flex items-center justify-between gap-2">
                <div class="text-[10px] uppercase tracking-wider text-fg-muted">
                  Next {{ recurrencePreview.upcoming.length }} of {{ recurrencePreview.totalShown }}
                </div>
                <div class="shrink-0 text-[10px] text-primary">
                  {{ recurrencePreview.cadence }}
                </div>
              </div>
              <div
                v-for="(p, idx) in recurrencePreview.upcoming"
                :key="idx"
                :data-testid="`txnform.preview.${idx}`"
                class="flex items-baseline justify-between text-[11px] tabular"
              >
                <span class="text-fg-muted">{{ formatPreviewDate(p.effective_date) }}</span>
                <span :class="p.amount_k > 0 ? 'text-positive' : 'text-negative'">
                  {{ p.amount_k > 0 ? '+' : '' }}{{ p.amount_k.toFixed(2) }}k
                </span>
              </div>
              <div
                v-if="recurrencePreview.totalShown > recurrencePreview.upcoming.length"
                class="mt-1 text-[10px] text-fg-muted"
              >
                +{{ recurrencePreview.totalShown - recurrencePreview.upcoming.length }} more inside the timeline
              </div>
            </div>
          </div>

          <!-- Description -->
          <UiField class="mb-2">
            <template #label>Description</template>
            <template #default="{ id, describedBy }">
              <input
                data-testid="txnform.description"
                v-model="description"
                :id="id"
                :aria-describedby="describedBy"
                type="text"
                :placeholder="isRecurring ? 'HM interest, 123 Main' : 'Rehab draw #2, 123 Main St'"
                maxlength="500"
                class="ui-input"
              />
            </template>
          </UiField>

          <!-- Actions -->
          <template #footer>
            <div class="flex flex-wrap justify-end gap-3">
              <UiButton
                data-testid="txnform.cancel"
                variant="ghost"
                @click="$emit('close')"
              >
                Cancel
              </UiButton>
              <UiButton
                data-testid="txnform.save"
                :disabled="!isValid"
                :variant="isOutflow ? 'danger' : 'primary'"
                @click="onSave"
              >
                {{ isEditing ? 'Update' : (isRecurring ? 'Create Series' : 'Add') }}
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
/*
 * The panel's own scale, keyed off a class this file owns rather than the
 * `.relative` utility the panel happened to carry.
 */
.modal-enter-active .modal-panel, .modal-leave-active .modal-panel {
  transition: transform var(--dur-fast) var(--ease-standard);
}
.modal-enter-from .modal-panel, .modal-leave-to .modal-panel {
  transform: scale(0.95);
}
</style>
