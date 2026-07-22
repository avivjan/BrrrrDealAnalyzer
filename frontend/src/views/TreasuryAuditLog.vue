<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useTreasuryStore } from '../stores/treasuryStore'
import AuditLogTable from '../components/treasury/AuditLogTable.vue'

const router = useRouter()
const store = useTreasuryStore()

const toast = ref('')
const toastVisible = ref(false)
let toastTimer: ReturnType<typeof setTimeout> | undefined

onMounted(async () => {
  try {
    await store.fetchAll()
  } catch {
    showToast(store.error ?? 'Failed to load audit log')
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

function extractErrorMessage(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  return typeof detail === 'string' && detail.length > 0 ? detail : fallback
}

async function onPatchTransaction(transactionId: string, field: string, value: number | boolean | string | null) {
  try {
    await store.patchTransaction(transactionId, { [field]: value } as never)
  } catch (err) {
    showToast(extractErrorMessage(err, `Failed to save ${field}`))
  }
}

async function onDeleteTransaction(transactionId: string) {
  if (!window.confirm('Delete this transaction?')) return
  try {
    await store.removeTransaction(transactionId)
  } catch (err) {
    showToast(extractErrorMessage(err, 'Failed to delete transaction'))
  }
}

async function onAddTransaction() {
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
  } catch (err) {
    showToast(extractErrorMessage(err, 'Failed to create transaction'))
  }
}
</script>

<template>
  <div class="audit-page">
    <header class="page-header">
      <div class="flex items-center gap-3">
        <button class="back-btn" title="Back to Reserve & Treasury" @click="router.push('/treasury')">
          <i class="pi pi-arrow-left"></i>
        </button>
        <div>
          <h1 class="page-title">Transaction Audit Log</h1>
          <p class="page-subtitle">Every ledger entry, editable in place</p>
        </div>
      </div>

      <div class="header-actions">
        <button class="icon-btn" :disabled="store.loading" title="Refresh" @click="store.fetchAll()">
          <i class="pi pi-refresh" :class="{ spin: store.loading }"></i>
        </button>
      </div>
    </header>

    <main class="page-body">
      <AuditLogTable
        :transactions="store.transactions"
        :properties="store.properties"
        :llcs="store.llcs"
        :disabled="store.loading"
        @patch="onPatchTransaction"
        @delete="onDeleteTransaction"
        @add="onAddTransaction"
      />
    </main>

    <Transition name="toast">
      <div v-if="toastVisible" class="toast">{{ toast }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.audit-page {
  min-height: 100vh;
  background: linear-gradient(160deg, #020617 0%, #0b0f1f 45%, #0f172a 100%);
  color: #e2e8f0;
}

.page-header {
  position: sticky;
  top: 0;
  z-index: 30;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.9rem 1.5rem;
  background: rgba(2, 6, 23, 0.85);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(10px);
}

.back-btn,
.icon-btn {
  width: 2.25rem;
  height: 2.25rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.65rem;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.7);
  border: none;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.back-btn:hover,
.icon-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  color: white;
}

.icon-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-title {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 800;
  color: white;
  letter-spacing: -0.01em;
}

.page-subtitle {
  margin: 0.05rem 0 0;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.page-body {
  padding: 1.5rem;
  max-width: 1440px;
  margin: 0 auto;
}

.toast {
  position: fixed;
  bottom: 1.5rem;
  left: 50%;
  transform: translateX(-50%);
  max-width: min(90vw, 560px);
  background: #1e293b;
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 0.65rem 1.1rem;
  border-radius: 999px;
  font-size: 0.85rem;
  text-align: center;
  z-index: 80;
  box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.6);
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
