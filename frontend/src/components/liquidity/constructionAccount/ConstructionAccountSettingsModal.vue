<script setup lang="ts">
/**
 * Link a construction account to a Bought BRRRR deal, or change the link's settings (tasks/todo/ConstructionAccountPerRehab.md):
 * the construction account and the same LLC's checking, picked from the Mercury accounts; the two "before this
 * account" amounts (a rehab linked mid-way); and the buffer to keep. There is no deposit target: what goes in is the
 * deal's rehab cushion, edited on the card. Saving goes through the timeline prompt.
 */
import { computed, ref, watch } from 'vue'

import { liquidityApi } from '../../../api/liquidity'
import { useConstructionAccountStore } from '../../../stores/constructionAccountStore'
import type { ConstructionAccountStatus } from '../../../types/constructionAccount'
import type { MercuryAccountSummary } from '../../../types/liquidity'
import { mercuryAccountDisplayName } from '../../../utils/mercuryAccountDisplayName'
import { formatMoney } from '../../../utils/money'

const props = defineProps<{ open: boolean; status: ConstructionAccountStatus | null }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const store = useConstructionAccountStore()
const accounts = ref<MercuryAccountSummary[]>([])
const loadingAccounts = ref(false)
const errorMessage = ref<string | null>(null)
const isSaving = ref(false)
const constructionAccountId = ref('')
const checkingAccountId = ref('')
const drawsBefore = ref('0')
const paidBefore = ref('0')
const buffer = ref('0')

const isEditingALink = computed(() => !!props.status?.is_linked)
const activeAccounts = computed(() => accounts.value.filter(account => account.status === 'active'))
const chosenConstructionAccount = computed(() => activeAccounts.value.find(account => account.id === constructionAccountId.value))
const constructionAccountChoices = computed(() => activeAccounts.value.filter(account =>
  !account.is_a_linked_construction_account || account.id === props.status?.construction_account?.mercury_account_id))
const checkingChoices = computed(() => activeAccounts.value.filter(account =>
  account.id !== constructionAccountId.value && account.is_counted_as_cash
  && (!chosenConstructionAccount.value || account.workspace === chosenConstructionAccount.value.workspace)))

watch(() => props.open, async (open) => {
  if (!open || !props.status) return
  errorMessage.value = null
  constructionAccountId.value = props.status.construction_account?.mercury_account_id ?? ''
  checkingAccountId.value = props.status.primary_checking_account?.mercury_account_id ?? ''
  drawsBefore.value = String(props.status.loan_draws_pulled_before_construction_account_dollars ?? 0)
  paidBefore.value = String(props.status.rehab_payments_made_before_construction_account_dollars ?? 0)
  buffer.value = String(props.status.minimum_balance_to_keep_in_construction_account_dollars ?? 0)
  loadingAccounts.value = true
  try {
    accounts.value = (await liquidityApi.getMercuryBalance()).accounts
  } catch {
    errorMessage.value = 'The Mercury accounts could not be read. Check the Mercury connection in the settings, then try again.'
  } finally {
    loadingAccounts.value = false
  }
})

function amountOf(typed: string): number | null {
  const value = Number(typed)
  return Number.isFinite(value) && value >= 0 ? Math.round(value * 100) / 100 : null
}

async function save() {
  if (!props.status) return
  const draws = amountOf(drawsBefore.value), paid = amountOf(paidBefore.value), kept = amountOf(buffer.value)
  if (!constructionAccountId.value || !checkingAccountId.value || draws === null || paid === null || kept === null) {
    errorMessage.value = 'Pick both accounts, and enter amounts of $0 or more.'
    return
  }
  isSaving.value = true
  errorMessage.value = null
  try {
    const saved = await store.saveLink(props.status.bought_deal_id, {
      construction_mercury_account_id: constructionAccountId.value, primary_checking_mercury_account_id: checkingAccountId.value,
      loan_draws_pulled_before_construction_account_dollars: draws, rehab_payments_made_before_construction_account_dollars: paid,
      minimum_balance_to_keep_in_construction_account_dollars: kept,
    }, isEditingALink.value ? 'Change the construction account settings' : 'Link the construction account')
    if (saved) emit('close')
  } catch (error) {
    const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
    errorMessage.value = typeof detail === 'string' ? detail : 'The link could not be saved.'
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open && status" data-testid="ca-link.root" class="fixed inset-0 z-50 flex items-center justify-center p-4" @keydown.escape="emit('close')">
        <div class="absolute inset-0 bg-fg/50 md:backdrop-blur-sm" @click="emit('close')" />
        <UiModalPanel size="md" labelled-by="ca-link-title" class="modal-panel relative">
          <template #header>
            <div>
              <h2 id="ca-link-title" class="font-display text-lg font-semibold tracking-display text-fg">
                {{ isEditingALink ? 'Construction account settings' : 'Link a construction account' }}
              </h2>
              <p class="mt-1 text-sm text-fg-muted">{{ status.deal_address }}</p>
            </div>
          </template>
          <div class="space-y-4">
            <p v-if="loadingAccounts" class="text-sm text-fg-muted">Reading your Mercury accounts…</p>
            <p v-if="errorMessage" data-testid="ca-link.error" role="alert" class="rounded-ctl border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">{{ errorMessage }}</p>

            <UiField>
              <template #label>Construction account</template>
              <template #default="{ id, describedBy }">
                <select :id="id" v-model="constructionAccountId" :aria-describedby="describedBy" :disabled="isEditingALink" data-testid="ca-link.construction-account" class="ui-input">
                  <option value="" disabled>Pick the rehab's own account</option>
                  <option v-for="account in constructionAccountChoices" :key="account.id" :value="account.id">
                    {{ mercuryAccountDisplayName(account) }} · {{ account.workspace }} · {{ formatMoney(account.current_balance_dollars) }}
                  </option>
                </select>
              </template>
              <template #helper>{{ isEditingALink ? 'To use another account, use Switch account on the card.' : 'The lender wires the draws here; every rehab payment leaves from it.' }}</template>
            </UiField>

            <UiField>
              <template #label>Checking (same LLC)</template>
              <template #default="{ id, describedBy }">
                <select :id="id" v-model="checkingAccountId" :aria-describedby="describedBy" data-testid="ca-link.checking-account" class="ui-input">
                  <option value="" disabled>Pick the checking the deposit comes from</option>
                  <option v-for="account in checkingChoices" :key="account.id" :value="account.id">
                    {{ mercuryAccountDisplayName(account) }} · {{ formatMoney(account.current_balance_dollars) }}
                  </option>
                </select>
              </template>
              <template #helper>Only accounts counted as cash in the same Mercury workspace (LLC).</template>
            </UiField>

            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <UiField>
                <template #label>Loan draws pulled before ($)</template>
                <template #default="{ id }"><input :id="id" v-model="drawsBefore" data-testid="ca-link.draws-before" type="number" min="0" step="0.01" class="ui-input numeric" /></template>
                <template #helper>A rehab already running: draws that landed elsewhere.</template>
              </UiField>
              <UiField>
                <template #label>Rehab paid before ($)</template>
                <template #default="{ id }"><input :id="id" v-model="paidBefore" data-testid="ca-link.paid-before" type="number" min="0" step="0.01" class="ui-input numeric" /></template>
                <template #helper>Rehab already paid from somewhere else.</template>
              </UiField>
            </div>
            <UiField>
              <template #label>Buffer to keep in the account ($)</template>
              <template #default="{ id }"><input :id="id" v-model="buffer" data-testid="ca-link.buffer" type="number" min="0" step="1" class="ui-input numeric" /></template>
              <template #helper>For reimbursement draws: lowers what is safe to steal. Editable later on the card.</template>
            </UiField>
          </div>
          <template #footer>
            <div class="flex justify-end gap-3">
              <UiButton variant="ghost" data-testid="ca-link.cancel" @click="emit('close')">Cancel</UiButton>
              <UiButton data-testid="ca-link.save" :loading="isSaving" :disabled="loadingAccounts" @click="save">{{ isEditingALink ? 'Save' : 'Link' }}</UiButton>
            </div>
          </template>
        </UiModalPanel>
      </div>
    </Transition>
  </Teleport>
</template>
