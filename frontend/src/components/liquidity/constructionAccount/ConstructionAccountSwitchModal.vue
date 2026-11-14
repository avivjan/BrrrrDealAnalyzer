<script setup lang="ts">
/**
 * Replace a deal's construction account mid-rehab (tasks/todo/ConstructionAccountPerRehab.md). The old account must be
 * empty first (move its balance to the new one in Mercury); its draws and payments carry over as the "before this
 * account" amounts, prefilled and editable. Saving goes through the timeline prompt.
 */
import { computed, ref, watch } from 'vue'

import { constructionAccountApi } from '../../../api/constructionAccount'
import { liquidityApi } from '../../../api/liquidity'
import { useConstructionAccountStore } from '../../../stores/constructionAccountStore'
import type { ConstructionAccountStatus, ConstructionAccountSwitchPreview } from '../../../types/constructionAccount'
import type { MercuryAccountSummary } from '../../../types/liquidity'
import { mercuryAccountDisplayName } from '../../../utils/mercuryAccountDisplayName'
import { formatMoney } from '../../../utils/money'

const props = defineProps<{ open: boolean; status: ConstructionAccountStatus | null }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const store = useConstructionAccountStore()
const preview = ref<ConstructionAccountSwitchPreview | null>(null)
const accounts = ref<MercuryAccountSummary[]>([])
const newAccountId = ref('')
const drawsBefore = ref('0')
const paidBefore = ref('0')
const isLoading = ref(false)
const isSaving = ref(false)
const errorMessage = ref<string | null>(null)

const newAccountChoices = computed(() => accounts.value.filter(account => account.status === 'active' && !account.is_a_linked_construction_account
  && account.workspace === props.status?.mercury_workspace_label && account.id !== props.status?.primary_checking_account?.mercury_account_id))

async function load() {
  if (!props.status) return
  isLoading.value = true
  errorMessage.value = null
  try {
    const [switchPreview, balance] = await Promise.all([constructionAccountApi.switchPreview(props.status.bought_deal_id), liquidityApi.getMercuryBalance()])
    preview.value = switchPreview
    accounts.value = balance.accounts
    drawsBefore.value = String(switchPreview.loan_draws_pulled_before_construction_account_dollars)
    paidBefore.value = String(switchPreview.rehab_payments_made_before_construction_account_dollars)
  } catch {
    errorMessage.value = 'Mercury could not be read. Try again in a moment.'
  } finally {
    isLoading.value = false
  }
}
watch(() => props.open, (open) => { if (open) { newAccountId.value = ''; void load() } })

async function save() {
  if (!props.status || !newAccountId.value) return
  isSaving.value = true
  errorMessage.value = null
  try {
    const saved = await store.switchAccount(props.status.bought_deal_id, {
      new_construction_mercury_account_id: newAccountId.value,
      loan_draws_pulled_before_construction_account_dollars: Math.max(0, Number(drawsBefore.value) || 0),
      rehab_payments_made_before_construction_account_dollars: Math.max(0, Number(paidBefore.value) || 0),
    })
    if (saved) emit('close')
  } catch (error) {
    const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
    errorMessage.value = typeof detail === 'string' ? detail : 'The account could not be switched.'
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open && status" data-testid="ca-switch.root" class="fixed inset-0 z-50 flex items-center justify-center p-4" @keydown.escape="emit('close')">
        <div class="absolute inset-0 bg-fg/50 md:backdrop-blur-sm" @click="emit('close')" />
        <UiModalPanel size="md" labelled-by="ca-switch-title" class="modal-panel relative">
          <template #header>
            <div>
              <h2 id="ca-switch-title" class="font-display text-lg font-semibold tracking-display text-fg">Switch the construction account</h2>
              <p class="mt-1 text-sm text-fg-muted">{{ status.deal_address }} · now {{ status.construction_account?.name }}</p>
            </div>
          </template>
          <div class="space-y-4">
            <p v-if="isLoading" class="text-sm text-fg-muted">Reading the old account…</p>
            <p v-if="errorMessage" data-testid="ca-switch.error" role="alert" class="rounded-ctl border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">{{ errorMessage }}</p>
            <p v-if="preview?.old_account_must_be_emptied_first" data-testid="ca-switch.empty-first" role="alert"
               class="rounded-ctl border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
              Move {{ formatMoney(preview.old_construction_account_balance_dollars) }} to the new account first (in Mercury), then switch.
              <button type="button" class="ml-1 underline" data-testid="ca-switch.check-again" @click="load">Check again</button>
            </p>
            <UiField>
              <template #label>New construction account</template>
              <template #default="{ id }">
                <select :id="id" v-model="newAccountId" data-testid="ca-switch.new-account" class="ui-input">
                  <option value="" disabled>Pick an account of the same LLC</option>
                  <option v-for="account in newAccountChoices" :key="account.id" :value="account.id">{{ mercuryAccountDisplayName(account) }}</option>
                </select>
              </template>
            </UiField>
            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <UiField>
                <template #label>Loan draws pulled before ($)</template>
                <template #default="{ id }"><input :id="id" v-model="drawsBefore" data-testid="ca-switch.draws-before" type="number" min="0" step="0.01" class="ui-input numeric" /></template>
                <template #helper>Prefilled: what was before + the old account's draws.</template>
              </UiField>
              <UiField>
                <template #label>Rehab paid before ($)</template>
                <template #default="{ id }"><input :id="id" v-model="paidBefore" data-testid="ca-switch.paid-before" type="number" min="0" step="0.01" class="ui-input numeric" /></template>
                <template #helper>Prefilled: what was before + the old account's payments.</template>
              </UiField>
            </div>
          </div>
          <template #footer>
            <div class="flex justify-end gap-3">
              <UiButton variant="ghost" data-testid="ca-switch.cancel" @click="emit('close')">Cancel</UiButton>
              <UiButton data-testid="ca-switch.save" :loading="isSaving" :disabled="!newAccountId || !!preview?.old_account_must_be_emptied_first || isLoading" @click="save">Switch</UiButton>
            </div>
          </template>
        </UiModalPanel>
      </div>
    </Transition>
  </Teleport>
</template>
