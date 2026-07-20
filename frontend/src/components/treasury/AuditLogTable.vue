<script setup lang="ts">
import type { LLCConfiguration, PropertyStatus, TransactionLedger, TransactionType } from '../../types/treasury'
import { SUB_BUCKET_OPTIONS, TRANSACTION_TYPE_OPTIONS } from '../../types/treasury'
import InlineEditValue from './InlineEditValue.vue'
import ToggleSwitch from './ToggleSwitch.vue'

defineProps<{
  transactions: TransactionLedger[]
  properties: PropertyStatus[]
  llcs: LLCConfiguration[]
  disabled?: boolean
}>()

const emit = defineEmits<{
  patch: [transactionId: string, field: string, value: number | boolean | string | null]
  delete: [transactionId: string]
  add: []
}>()
</script>

<template>
  <section class="audit-log">
    <div class="mb-3 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <i class="pi pi-list text-indigo-400"></i>
        <h2 class="text-sm font-bold text-white">Transaction Audit Log</h2>
        <span class="text-[0.7rem] text-white/35">{{ transactions.length }} entries</span>
      </div>
      <button class="add-txn-btn" @click="emit('add')">
        <i class="pi pi-plus"></i> Add Transaction
      </button>
    </div>

    <div v-if="transactions.length === 0" class="empty-state">No transactions logged yet.</div>

    <div v-else class="table-scroll">
      <table class="audit-table">
        <thead>
          <tr>
            <th>Property</th>
            <th>Amount</th>
            <th>Description</th>
            <th>Timestamp</th>
            <th>Sub Bucket</th>
            <th>Type</th>
            <th>Batch ID</th>
            <th>Real Tx</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="txn in transactions" :key="txn.transaction_id">
            <td>
              <select
                class="dark-select"
                :value="txn.property_id ?? ''"
                :disabled="disabled"
                @change="emit('patch', txn.transaction_id, 'property_id', ($event.target as HTMLSelectElement).value || null)"
              >
                <option value="">Unassigned</option>
                <option v-for="prop in properties" :key="prop.property_id" :value="prop.property_id">
                  {{ prop.property_id }}
                </option>
              </select>
            </td>
            <td>
              <InlineEditValue
                :model-value="txn.amount"
                type="number"
                currency
                :decimals="2"
                :disabled="disabled"
                class="font-semibold"
                :class="txn.amount < 0 ? 'text-rose-400' : 'text-emerald-300'"
                @commit="(v) => emit('patch', txn.transaction_id, 'amount', v)"
              />
            </td>
            <td>
              <InlineEditValue
                :model-value="txn.description"
                :disabled="disabled"
                class="text-white/80"
                @commit="(v) => emit('patch', txn.transaction_id, 'description', v)"
              />
            </td>
            <td>
              <input
                type="datetime-local"
                class="dark-select [color-scheme:dark]"
                :value="txn.timestamp.slice(0, 16)"
                :disabled="disabled"
                @change="
                  emit(
                    'patch',
                    txn.transaction_id,
                    'timestamp',
                    new Date(($event.target as HTMLInputElement).value).toISOString(),
                  )
                "
              />
            </td>
            <td>
              <select
                class="dark-select"
                :value="txn.sub_bucket_assignment ?? 'None'"
                :disabled="disabled"
                @change="
                  emit(
                    'patch',
                    txn.transaction_id,
                    'sub_bucket_assignment',
                    ($event.target as HTMLSelectElement).value === 'None'
                      ? null
                      : ($event.target as HTMLSelectElement).value,
                  )
                "
              >
                <option v-for="opt in SUB_BUCKET_OPTIONS" :key="String(opt)" :value="opt ?? 'None'">
                  {{ opt ?? 'None' }}
                </option>
              </select>
            </td>
            <td>
              <select
                class="dark-select"
                :value="txn.transaction_type"
                :disabled="disabled"
                @change="
                  emit(
                    'patch',
                    txn.transaction_id,
                    'transaction_type',
                    ($event.target as HTMLSelectElement).value as TransactionType,
                  )
                "
              >
                <option v-for="opt in TRANSACTION_TYPE_OPTIONS" :key="opt" :value="opt">{{ opt }}</option>
              </select>
            </td>
            <td>
              <InlineEditValue
                :model-value="txn.settlement_batch_id ?? ''"
                empty-label="—"
                :disabled="disabled"
                class="text-white/50"
                @commit="(v) => emit('patch', txn.transaction_id, 'settlement_batch_id', v)"
              />
            </td>
            <td>
              <ToggleSwitch
                :model-value="txn.is_real_bank_tx"
                :disabled="disabled"
                @update:model-value="(v) => emit('patch', txn.transaction_id, 'is_real_bank_tx', v)"
              />
            </td>
            <td>
              <button class="row-delete" @click="emit('delete', txn.transaction_id)">
                <i class="pi pi-trash"></i>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.audit-log {
  border-radius: 1.25rem;
  background: rgba(15, 23, 42, 0.65);
  border: 1px solid rgba(255, 255, 255, 0.07);
  padding: 1.1rem 1.2rem 1.35rem;
  box-shadow: 0 24px 60px -30px rgba(0, 0, 0, 0.7);
}

.add-txn-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 0.85rem;
  border-radius: 0.6rem;
  background: rgba(99, 102, 241, 0.15);
  color: #a5b4fc;
  font-size: 0.78rem;
  font-weight: 700;
  border: 1px solid rgba(99, 102, 241, 0.25);
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.add-txn-btn:hover {
  background: rgba(99, 102, 241, 0.25);
}

.empty-state {
  padding: 2rem 0;
  text-align: center;
  font-size: 0.82rem;
  color: rgba(255, 255, 255, 0.3);
}

.table-scroll {
  overflow-x: auto;
}

.audit-table {
  width: 100%;
  min-width: 900px;
  border-collapse: collapse;
  font-size: 0.8rem;
}

.audit-table thead th {
  text-align: left;
  padding: 0.5rem 0.55rem;
  font-size: 0.63rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: rgba(255, 255, 255, 0.35);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  white-space: nowrap;
}

.audit-table tbody td {
  padding: 0.5rem 0.55rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  vertical-align: middle;
}

.dark-select {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 0.45rem;
  color: rgba(255, 255, 255, 0.8);
  font-size: 0.76rem;
  padding: 0.3rem 0.4rem;
  outline: none;
  max-width: 150px;
}

.dark-select:disabled {
  opacity: 0.5;
}

.row-delete {
  color: rgba(255, 255, 255, 0.3);
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0.2rem;
  transition: color 0.15s ease;
}

.row-delete:hover {
  color: #fb7185;
}
</style>
