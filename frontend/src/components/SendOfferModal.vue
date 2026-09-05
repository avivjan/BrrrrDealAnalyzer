<script setup lang="ts">
import { ref } from 'vue';
import api from '../api';
import MoneyInput from './ui/MoneyInput.vue';

defineProps<{
  isOpen: boolean;
}>();

const emit = defineEmits(['close']);

const form = ref({
  agent_name: '',
  agent_email: '',
  property_address: '',
  purchase_price: 0,
  inspection_period_days: 0
});

const loading = ref(false);
const message = ref<{ type: 'success' | 'error'; text: string } | null>(null);

const closeModal = () => {
  message.value = null;
  // Reset form only if successful or if user wants to clear? 
  // Maybe better to keep inputs if cancelled accidentally.
  emit('close');
};

const sendOffer = async () => {
  if (!form.value.agent_name || !form.value.agent_email || !form.value.property_address || !form.value.purchase_price) {
     message.value = { type: 'error', text: 'Please fill in all required fields.' };
     return;
  }
  
  loading.value = true;
  message.value = null;
  
  try {
    const res = await api.sendOffer({
        agent_name: form.value.agent_name,
        agent_email: form.value.agent_email,
        property_address: form.value.property_address,
        purchase_price: form.value.purchase_price,
        inspection_period_days: form.value.inspection_period_days
    });
    
    if (res.success) {
      message.value = { type: 'success', text: 'Offer sent successfully!' };
      setTimeout(() => {
          closeModal();
          // Reset form after success
          form.value = {
            agent_name: '',
            agent_email: '',
            property_address: '',
            purchase_price: 0,
            inspection_period_days: 0
          };
      }, 1500);
    } else {
      message.value = { type: 'error', text: res.message || 'Failed to send offer.' };
    }
  } catch (error: any) {
    message.value = { type: 'error', text: error.response?.data?.detail || 'An unexpected error occurred.' };
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <div
    v-if="isOpen"
    data-testid="offer.root"
    class="fixed inset-0 z-50 flex items-center justify-center bg-fg/40 p-4 md:backdrop-blur-sm"
    @click.self="closeModal"
  >
    <UiModalPanel size="sm" labelled-by="offer-modal-title">
      <!-- Header -->
      <template #header>
        <div class="flex items-center justify-between gap-3">
          <h3
            id="offer-modal-title"
            class="min-w-0 text-base font-semibold text-fg md:text-lg"
          >
            Send Market Offer
          </h3>
          <UiIconButton
            data-testid="offer.close"
            @click="closeModal"
            label="Close"
            size="md"
          >
            <i class="pi pi-times text-lg" aria-hidden="true"></i>
          </UiIconButton>
        </div>
      </template>

      <!-- Body -->
      <div class="space-y-4">
        <div
          v-if="message"
          data-testid="offer.message"
          :class="`p-3 rounded-ctl text-sm font-medium ${message.type === 'success' ? 'text-positive bg-positive/10' : 'text-negative bg-negative/10'}`"
        >
          {{ message.text }}
        </div>

        <UiField>
          <template #label>Agent Name *</template>
          <template #default="{ id, describedBy }">
            <input
              data-testid="offer.agent-name"
              v-model="form.agent_name"
              :id="id"
              :aria-describedby="describedBy"
              type="text"
              class="ui-input"
              placeholder="e.g. John Doe"
            />
          </template>
        </UiField>

        <UiField>
          <template #label>Agent Email *</template>
          <template #default="{ id, describedBy }">
            <input
              data-testid="offer.agent-email"
              v-model="form.agent_email"
              :id="id"
              :aria-describedby="describedBy"
              type="email"
              class="ui-input"
              placeholder="agent@example.com"
            />
          </template>
        </UiField>

        <UiField>
          <template #label>Property Address *</template>
          <template #default="{ id, describedBy }">
            <input
              data-testid="offer.property-address"
              v-model="form.property_address"
              :id="id"
              :aria-describedby="describedBy"
              type="text"
              class="ui-input"
              placeholder="123 Main St"
            />
          </template>
        </UiField>

        <!--
          `MoneyInput` is already a field of its own — it renders the label the
          `for`/`id` pair points at, and its own required marker — so wrapping
          it in `UiField` would give it a second label.
        -->
        <MoneyInput
          data-testid="offer.purchase-price"
          label="Purchase Price"
          v-model="form.purchase_price"
          :required="true"
        />

        <UiField>
          <template #label>Inspection Period (Days)</template>
          <template #default="{ id, describedBy }">
            <input
              data-testid="offer.inspection-days"
              v-model.number="form.inspection_period_days"
              :id="id"
              :aria-describedby="describedBy"
              type="number"
              class="ui-input"
              placeholder="e.g. 7"
            />
          </template>
        </UiField>
      </div>

      <!-- Footer -->
      <template #footer>
        <div class="flex flex-wrap items-center justify-end gap-2">
          <UiButton
            data-testid="offer.cancel"
            @click="closeModal"
            variant="ghost"
          >
            Cancel
          </UiButton>
          <UiButton data-testid="offer.send" @click="sendOffer" :disabled="loading">
            <i class="pi pi-spin pi-spinner" v-if="loading" aria-hidden="true"></i>
            {{ loading ? 'Sending...' : 'Send Offer' }}
          </UiButton>
        </div>
      </template>
    </UiModalPanel>
  </div>
</template>
