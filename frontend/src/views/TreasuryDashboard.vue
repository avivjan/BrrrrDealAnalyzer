<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useTreasuryStore } from '../stores/treasuryStore'
import type {
  LLCConfiguration,
  PropertyStatus,
  TransactionLedger,
  PropertyCashFlowHistory,
  TransactionType,
} from '../types/treasury'
import {
  SUB_BUCKET_OPTIONS,
  TRANSACTION_TYPE_OPTIONS,
} from '../types/treasury'

const router = useRouter()
const store = useTreasuryStore()

type TabKey = 'llcs' | 'properties' | 'transactions' | 'history'
const activeTab = ref<TabKey>('llcs')
const toast = ref('')
const toastVisible = ref(false)
let toastTimer: ReturnType<typeof setTimeout> | undefined

const tabs: Array<{ key: TabKey; label: string; icon: string }> = [
  { key: 'llcs', label: 'LLC Config', icon: 'pi-building' },
  { key: 'properties', label: 'Property Status', icon: 'pi-home' },
  { key: 'transactions', label: 'Transaction Ledger', icon: 'pi-list' },
  { key: 'history', label: 'Cash Flow History', icon: 'pi-chart-bar' },
]

const llcNameById = computed(() =>
  Object.fromEntries(store.llcs.map((llc) => [llc.llc_id, llc.llc_name])),
)

onMounted(async () => {
  try {
    await store.fetchAll()
  } catch {
    showToast(store.error ?? 'Failed to load treasury data')
  }
})

function showToast(message: string) {
  toast.value = message
  toastVisible.value = true
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastVisible.value = false
  }, 3200)
}

async function saveLlcField(llc: LLCConfiguration, field: 'llc_name' | 'checking_redline_buffer', raw: string) {
  const payload =
    field === 'checking_redline_buffer'
      ? { checking_redline_buffer: Number(raw) }
      : { llc_name: raw }
  try {
    await store.patchLlc(llc.llc_id, payload)
    showToast(`Saved ${field} for ${llc.llc_id}`)
  } catch {
    showToast(`Failed to save ${field}`)
  }
}

async function savePropertyField(
  prop: PropertyStatus,
  field: keyof PropertyStatus,
  raw: string | boolean,
) {
  const numericFields = new Set([
    'tax_bucket_balance',
    'tax_to_settle',
    'ins_bucket_balance',
    'ins_to_settle',
    'reserve_bucket_balance',
    'reserve_to_settle',
    'reserve_bucket_cap',
    'reserve_debt',
    'interest_earned_counter',
    'base_rent_target',
    'target_tax_allocation',
    'target_ins_allocation',
    'target_reserve_allocation',
  ])
  const value =
    typeof raw === 'boolean'
      ? raw
      : numericFields.has(field)
        ? Number(raw)
        : raw
  try {
    await store.patchProperty(prop.property_id, { [field]: value } as never)
    showToast(`Saved ${String(field)} for ${prop.property_id}`)
  } catch {
    showToast(`Failed to save ${String(field)}`)
  }
}

async function saveTransactionField(
  txn: TransactionLedger,
  field: keyof TransactionLedger,
  raw: string | boolean,
) {
  let value: unknown = raw
  if (field === 'amount') value = Number(raw)
  if (field === 'is_real_bank_tx') value = Boolean(raw)
  if (field === 'sub_bucket_assignment') {
    value = raw === 'None' ? null : raw
  }
  try {
    await store.patchTransaction(txn.transaction_id, { [field]: value } as never)
    showToast(`Saved ${String(field)} for ${txn.transaction_id.slice(0, 8)}…`)
  } catch {
    showToast(`Failed to save ${String(field)}`)
  }
}

async function saveHistoryField(
  row: PropertyCashFlowHistory,
  field: 'month_year' | 'monthly_cash_flow' | 'cumulative_cash_flow',
  raw: string,
) {
  const value = field === 'month_year' ? raw : Number(raw)
  try {
    await store.patchCashFlow(row.history_id, { [field]: value })
    showToast(`Saved ${field} for ${row.month_year}`)
  } catch {
    showToast(`Failed to save ${field}`)
  }
}

async function addLlc() {
  const name = window.prompt('LLC name?')
  if (!name?.trim()) return
  try {
    await store.createLlc({ llc_name: name.trim() })
    showToast('LLC created')
  } catch {
    showToast('Failed to create LLC')
  }
}

async function addProperty() {
  if (store.llcs.length === 0) {
    showToast('Create an LLC first')
    return
  }
  const propertyId = window.prompt('Property ID (optional — leave blank to auto-generate)?') ?? ''
  const llcId = store.llcs[0]?.llc_id
  if (!llcId) return
  try {
    await store.createProperty({
      llc_id: llcId,
      ...(propertyId.trim() ? { property_id: propertyId.trim() } : {}),
    })
    showToast('Property created')
  } catch {
    showToast('Failed to create property')
  }
}

async function addTransaction() {
  if (store.properties.length === 0) {
    showToast('Create a property first')
    return
  }
  try {
    await store.createTransaction({
      property_id: store.properties[0]?.property_id ?? null,
      amount: 0,
      description: 'Manual entry',
      timestamp: new Date().toISOString(),
      transaction_type: 'Rent',
    })
    showToast('Transaction created')
  } catch {
    showToast('Failed to create transaction')
  }
}

async function addHistory() {
  if (store.properties.length === 0) {
    showToast('Create a property first')
    return
  }
  const month = window.prompt('Month (YYYY-MM)?', '2026-07')
  if (!month?.trim()) return
  try {
    await store.createCashFlow({
      property_id: store.properties[0]!.property_id,
      month_year: month.trim(),
    })
    showToast('Snapshot created')
  } catch {
    showToast('Failed to create snapshot')
  }
}

async function deleteLlc(id: string) {
  if (!window.confirm('Delete LLC and all child properties/history?')) return
  try {
    await store.removeLlc(id)
    showToast('LLC deleted')
  } catch {
    showToast('Failed to delete LLC')
  }
}

async function deleteProperty(id: string) {
  if (!window.confirm('Delete property and its cash-flow history?')) return
  try {
    await store.removeProperty(id)
    showToast('Property deleted')
  } catch {
    showToast('Failed to delete property')
  }
}

async function deleteTransaction(id: string) {
  if (!window.confirm('Delete transaction?')) return
  try {
    await store.removeTransaction(id)
    showToast('Transaction deleted')
  } catch {
    showToast('Failed to delete transaction')
  }
}

async function deleteHistory(id: string) {
  if (!window.confirm('Delete snapshot?')) return
  try {
    await store.removeCashFlow(id)
    showToast('Snapshot deleted')
  } catch {
    showToast('Failed to delete snapshot')
  }
}

const propertyNumericFields: Array<{ key: keyof PropertyStatus; label: string }> = [
  { key: 'tax_bucket_balance', label: 'Tax Balance' },
  { key: 'tax_to_settle', label: 'Tax To Settle' },
  { key: 'ins_bucket_balance', label: 'Ins Balance' },
  { key: 'ins_to_settle', label: 'Ins To Settle' },
  { key: 'reserve_bucket_balance', label: 'Reserve Balance' },
  { key: 'reserve_to_settle', label: 'Reserve To Settle' },
  { key: 'reserve_bucket_cap', label: 'Reserve Cap' },
  { key: 'reserve_debt', label: 'Reserve Debt' },
  { key: 'interest_earned_counter', label: 'Interest Counter' },
  { key: 'base_rent_target', label: 'Base Rent Target' },
  { key: 'target_tax_allocation', label: 'Tax Target' },
  { key: 'target_ins_allocation', label: 'Ins Target' },
  { key: 'target_reserve_allocation', label: 'Reserve Target' },
]
</script>

<template>
  <div class="treasury-page">
    <header class="page-header">
      <div class="header-left">
        <button class="back-btn" title="Back" @click="router.push('/')">
          <i class="pi pi-arrow-left"></i>
        </button>
        <div>
          <h1 class="page-title">Reserve & Treasury</h1>
          <p class="page-subtitle">Human-in-the-loop overrides for every balance and flag</p>
        </div>
      </div>
      <button class="refresh-btn" :disabled="store.loading" @click="store.fetchAll()">
        <i class="pi pi-refresh" :class="{ spin: store.loading }"></i>
        Refresh
      </button>
    </header>

    <nav class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        <i :class="['pi', tab.icon]"></i>
        {{ tab.label }}
      </button>
    </nav>

    <main class="panel">
      <section v-if="activeTab === 'llcs'" class="section">
        <div class="section-head">
          <h2>LLC Configuration</h2>
          <button class="primary-btn" @click="addLlc">Add LLC</button>
        </div>
        <div v-if="store.llcs.length === 0" class="empty">No LLCs yet.</div>
        <div v-for="llc in store.llcs" :key="llc.llc_id" class="card">
          <div class="card-head">
            <code>{{ llc.llc_id }}</code>
            <button class="danger-btn" @click="deleteLlc(llc.llc_id)">Delete</button>
          </div>
          <div class="field-grid">
            <label>
              LLC Name
              <input
                :value="llc.llc_name"
                @change="saveLlcField(llc, 'llc_name', ($event.target as HTMLInputElement).value)"
              />
            </label>
            <label>
              Checking Redline Buffer ($)
              <input
                type="number"
                step="0.01"
                :value="llc.checking_redline_buffer"
                @change="
                  saveLlcField(
                    llc,
                    'checking_redline_buffer',
                    ($event.target as HTMLInputElement).value,
                  )
                "
              />
            </label>
          </div>
        </div>
      </section>

      <section v-else-if="activeTab === 'properties'" class="section">
        <div class="section-head">
          <h2>Property Status</h2>
          <button class="primary-btn" @click="addProperty">Add Property</button>
        </div>
        <div v-if="store.properties.length === 0" class="empty">No properties yet.</div>
        <div v-for="prop in store.properties" :key="prop.property_id" class="card">
          <div class="card-head">
            <div>
              <code>{{ prop.property_id }}</code>
              <span class="muted"> · {{ llcNameById[prop.llc_id] ?? prop.llc_id }}</span>
            </div>
            <button class="danger-btn" @click="deleteProperty(prop.property_id)">Delete</button>
          </div>
          <div class="field-grid wide">
            <label>
              LLC
              <select
                :value="prop.llc_id"
                @change="savePropertyField(prop, 'llc_id', ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="llc in store.llcs" :key="llc.llc_id" :value="llc.llc_id">
                  {{ llc.llc_name }}
                </option>
              </select>
            </label>
            <label v-for="field in propertyNumericFields" :key="field.key">
              {{ field.label }}
              <input
                type="number"
                step="0.0001"
                :value="prop[field.key] as number"
                @change="
                  savePropertyField(prop, field.key, ($event.target as HTMLInputElement).value)
                "
              />
            </label>
            <label class="checkbox-label">
              <input
                type="checkbox"
                :checked="prop.force_tax_ins_accrual"
                @change="
                  savePropertyField(
                    prop,
                    'force_tax_ins_accrual',
                    ($event.target as HTMLInputElement).checked,
                  )
                "
              />
              Force Tax/Ins Accrual
            </label>
            <label class="checkbox-label">
              <input
                type="checkbox"
                :checked="prop.double_reserve_on_recovery"
                @change="
                  savePropertyField(
                    prop,
                    'double_reserve_on_recovery',
                    ($event.target as HTMLInputElement).checked,
                  )
                "
              />
              Double Reserve On Recovery
            </label>
          </div>
        </div>
      </section>

      <section v-else-if="activeTab === 'transactions'" class="section">
        <div class="section-head">
          <h2>Transaction Ledger</h2>
          <button class="primary-btn" @click="addTransaction">Add Transaction</button>
        </div>
        <div v-if="store.transactions.length === 0" class="empty">No transactions yet.</div>
        <div v-for="txn in store.transactions" :key="txn.transaction_id" class="card">
          <div class="card-head">
            <code>{{ txn.transaction_id.slice(0, 12) }}…</code>
            <button class="danger-btn" @click="deleteTransaction(txn.transaction_id)">Delete</button>
          </div>
          <div class="field-grid wide">
            <label>
              Property
              <select
                :value="txn.property_id ?? ''"
                @change="
                  saveTransactionField(txn, 'property_id', ($event.target as HTMLSelectElement).value)
                "
              >
                <option value="">None</option>
                <option v-for="prop in store.properties" :key="prop.property_id" :value="prop.property_id">
                  {{ prop.property_id }}
                </option>
              </select>
            </label>
            <label>
              Amount ($)
              <input
                type="number"
                step="0.01"
                :value="txn.amount"
                @change="saveTransactionField(txn, 'amount', ($event.target as HTMLInputElement).value)"
              />
            </label>
            <label>
              Description
              <input
                :value="txn.description"
                @change="
                  saveTransactionField(txn, 'description', ($event.target as HTMLInputElement).value)
                "
              />
            </label>
            <label>
              Timestamp
              <input
                type="datetime-local"
                :value="txn.timestamp.slice(0, 16)"
                @change="
                  saveTransactionField(
                    txn,
                    'timestamp',
                    new Date(($event.target as HTMLInputElement).value).toISOString(),
                  )
                "
              />
            </label>
            <label>
              Sub Bucket
              <select
                :value="txn.sub_bucket_assignment ?? 'None'"
                @change="
                  saveTransactionField(
                    txn,
                    'sub_bucket_assignment',
                    ($event.target as HTMLSelectElement).value,
                  )
                "
              >
                <option v-for="opt in SUB_BUCKET_OPTIONS" :key="String(opt)" :value="opt ?? 'None'">
                  {{ opt ?? 'None' }}
                </option>
              </select>
            </label>
            <label>
              Transaction Type
              <select
                :value="txn.transaction_type"
                @change="
                  saveTransactionField(
                    txn,
                    'transaction_type',
                    ($event.target as HTMLSelectElement).value as TransactionType,
                  )
                "
              >
                <option v-for="opt in TRANSACTION_TYPE_OPTIONS" :key="opt" :value="opt">
                  {{ opt }}
                </option>
              </select>
            </label>
            <label>
              Settlement Batch ID
              <input
                :value="txn.settlement_batch_id ?? ''"
                @change="
                  saveTransactionField(
                    txn,
                    'settlement_batch_id',
                    ($event.target as HTMLInputElement).value,
                  )
                "
              />
            </label>
            <label class="checkbox-label">
              <input
                type="checkbox"
                :checked="txn.is_real_bank_tx"
                @change="
                  saveTransactionField(
                    txn,
                    'is_real_bank_tx',
                    ($event.target as HTMLInputElement).checked,
                  )
                "
              />
              Real Bank Transaction
            </label>
          </div>
        </div>
      </section>

      <section v-else class="section">
        <div class="section-head">
          <h2>Property Cash Flow History</h2>
          <button class="primary-btn" @click="addHistory">Add Snapshot</button>
        </div>
        <div v-if="store.cashFlowHistory.length === 0" class="empty">No snapshots yet.</div>
        <div v-for="row in store.cashFlowHistory" :key="row.history_id" class="card">
          <div class="card-head">
            <code>{{ row.property_id }}</code>
            <button class="danger-btn" @click="deleteHistory(row.history_id)">Delete</button>
          </div>
          <div class="field-grid">
            <label>
              Month (YYYY-MM)
              <input
                :value="row.month_year"
                @change="
                  saveHistoryField(row, 'month_year', ($event.target as HTMLInputElement).value)
                "
              />
            </label>
            <label>
              Monthly Cash Flow ($)
              <input
                type="number"
                step="0.01"
                :value="row.monthly_cash_flow"
                @change="
                  saveHistoryField(row, 'monthly_cash_flow', ($event.target as HTMLInputElement).value)
                "
              />
            </label>
            <label>
              Cumulative Cash Flow ($)
              <input
                type="number"
                step="0.01"
                :value="row.cumulative_cash_flow"
                @change="
                  saveHistoryField(
                    row,
                    'cumulative_cash_flow',
                    ($event.target as HTMLInputElement).value,
                  )
                "
              />
            </label>
          </div>
        </div>
      </section>
    </main>

    <transition name="toast">
      <div v-if="toastVisible" class="toast">{{ toast }}</div>
    </transition>
  </div>
</template>

<style scoped>
.treasury-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
}

.page-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.85rem 1.25rem;
  background: rgba(255, 255, 255, 0.92);
  border-bottom: 1px solid #e2e8f0;
  backdrop-filter: blur(8px);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.back-btn,
.refresh-btn,
.primary-btn,
.danger-btn,
.tab-btn {
  border: none;
  cursor: pointer;
  font: inherit;
}

.back-btn {
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 0.65rem;
  background: #f1f5f9;
  color: #475569;
}

.page-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 800;
  color: #0f172a;
}

.page-subtitle {
  margin: 0.1rem 0 0;
  font-size: 0.78rem;
  color: #64748b;
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.55rem 0.9rem;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
  font-weight: 600;
}

.tab-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.75rem 1.25rem 0;
}

.tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.55rem 0.85rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.85);
  color: #475569;
  border: 1px solid #e2e8f0;
}

.tab-btn.active {
  background: #4f46e5;
  color: white;
  border-color: #4f46e5;
}

.panel {
  padding: 1rem 1.25rem 2rem;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.85rem;
}

.section-head h2 {
  margin: 0;
  font-size: 1rem;
  color: #0f172a;
}

.primary-btn {
  padding: 0.5rem 0.85rem;
  border-radius: 0.65rem;
  background: #4f46e5;
  color: white;
  font-weight: 600;
}

.danger-btn {
  padding: 0.35rem 0.65rem;
  border-radius: 0.5rem;
  background: #fee2e2;
  color: #b91c1c;
  font-size: 0.78rem;
  font-weight: 600;
}

.card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 0.9rem;
  padding: 0.9rem;
  margin-bottom: 0.75rem;
  box-shadow: 0 8px 24px -18px rgba(15, 23, 42, 0.25);
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.muted {
  color: #64748b;
  font-size: 0.82rem;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.65rem;
}

.field-grid.wide {
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
}

label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #64748b;
}

input,
select {
  width: 100%;
  padding: 0.45rem 0.55rem;
  border: 1px solid #cbd5e1;
  border-radius: 0.55rem;
  font-size: 0.88rem;
  color: #0f172a;
  background: #fff;
}

.checkbox-label {
  flex-direction: row;
  align-items: center;
  text-transform: none;
  font-size: 0.85rem;
  color: #0f172a;
}

.empty {
  padding: 2rem;
  text-align: center;
  color: #64748b;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 0.9rem;
  border: 1px dashed #cbd5e1;
}

.toast {
  position: fixed;
  bottom: 1.25rem;
  left: 50%;
  transform: translateX(-50%);
  background: #0f172a;
  color: white;
  padding: 0.65rem 1rem;
  border-radius: 999px;
  font-size: 0.85rem;
  z-index: 50;
}

.spin {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, 8px);
}
</style>
