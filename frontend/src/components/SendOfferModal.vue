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
  <div v-if="isOpen" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" @click.self="closeModal">
    <div class="bg-white rounded-xl shadow-2xl w-full max-w-lg overflow-hidden transform transition-all">
      <!-- Header -->
      <div class="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50">
        <h3 class="text-xl font-bold text-gray-800">Send Market Offer</h3>
        <button @click="closeModal" class="text-gray-400 hover:text-gray-600 transition-colors">
          <i class="pi pi-times text-lg"></i>
        </button>
      </div>
      
      <!-- Body -->
      <div class="p-6 space-y-4">
        <div v-if="message" :class="`p-3 rounded-lg text-sm font-medium ${message.type === 'success' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`">
          {{ message.text }}
        </div>
        
        <div>
           <label class="block text-sm font-medium text-gray-700 mb-1">Agent Name *</label>
           <input v-model="form.agent_name" type="text" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none" placeholder="e.g. John Doe" />
        </div>
        
        <div>
           <label class="block text-sm font-medium text-gray-700 mb-1">Agent Email *</label>
           <input v-model="form.agent_email" type="email" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none" placeholder="agent@example.com" />
        </div>
        
        <div>
           <label class="block text-sm font-medium text-gray-700 mb-1">Property Address *</label>
           <input v-model="form.property_address" type="text" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none" placeholder="123 Main St" />
        </div>
        
        <MoneyInput label="Purchase Price" v-model="form.purchase_price" :required="true" />
        
        <div>
           <label class="block text-sm font-medium text-gray-700 mb-1">Inspection Period (Days)</label>
           <input v-model.number="form.inspection_period_days" type="number" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none" placeholder="e.g. 7" />
        </div>

      </div>
      
      <!-- Footer -->
      <div class="px-6 py-4 bg-gray-50 flex justify-end gap-3">
        <button @click="closeModal" class="px-4 py-2 text-gray-600 font-medium hover:bg-gray-100 rounded-lg transition-colors">Cancel</button>
        <button 
          @click="sendOffer" 
          :disabled="loading"
          class="px-4 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          <i v-if="loading" class="pi pi-spin pi-spinner"></i>
          {{ loading ? 'Sending...' : 'Send Offer' }}
        </button>
      </div>
    </div>
  </div>
</template>

