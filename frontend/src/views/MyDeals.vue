<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { useDealStore } from '../stores/dealStore';
import { VueDraggable } from 'vue-draggable-plus';
import DealCard from '../components/DealCard.vue';
import type { ActiveDealRes } from '../types';

const store = useDealStore();

const activeTab = ref(1); // 1=Wholesale, 2=Market, 3=OffMarket
const stages = [
  { id: 1, name: 'New', color: 'bg-blue-500/10 border-blue-500/30' },
  { id: 2, name: 'Working', color: 'bg-yellow-500/10 border-yellow-500/30' },
  { id: 3, name: 'Brought', color: 'bg-emerald-500/10 border-emerald-500/30' },
  { id: 4, name: 'Keep in Mind', color: 'bg-purple-500/10 border-purple-500/30' },
  { id: 5, name: 'Dead', color: 'bg-gray-500/10 border-gray-500/30' },
];

// Local state for each column to support drag-and-drop
const columns = ref<Record<number, ActiveDealRes[]>>({
  1: [], 2: [], 3: [], 4: [], 5: []
});

// Sync local columns with store data based on active tab
const refreshColumns = () => {
  const filteredDeals = store.deals.filter(d => d.section === activeTab.value);
  
  // Reset columns
  columns.value = { 1: [], 2: [], 3: [], 4: [], 5: [] };
  
  filteredDeals.forEach(deal => {
    if (columns.value[deal.stage]) {
      columns.value[deal.stage].push(deal);
    } else {
       // Fallback for invalid stage
       columns.value[1].push(deal);
    }
  });
};

watch(() => [store.deals, activeTab.value], () => {
  refreshColumns();
}, { deep: true });

onMounted(async () => {
  await store.fetchDeals();
  refreshColumns();
});

// Handle Drag End
const onDrop = (event: any, stageId: number) => {
  if (event.added) {
    const deal = event.added.element;
    store.updateDealStage(deal.id, stageId);
  }
};

// Modals
const showAddModal = ref(false);
const showDetailModal = ref(false);
const selectedDeal = ref<ActiveDealRes | null>(null);

const openDeal = (deal: ActiveDealRes) => {
  selectedDeal.value = deal;
  showDetailModal.value = true;
};
</script>

<template>
  <div class="h-screen flex flex-col bg-whale-dark text-ocean-50 overflow-hidden">
    <!-- Header -->
    <header class="flex-none p-4 md:px-8 flex justify-between items-center border-b border-whale-surface bg-whale-dark/95 backdrop-blur z-20">
      <div class="flex items-center gap-4">
        <button @click="$router.push('/')" class="text-ocean-300 hover:text-white transition-colors">
          <i class="pi pi-home text-xl"></i>
        </button>
        <h1 class="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-ocean-300 to-ocean-100 hidden md:block">
          My Deals
        </h1>
      </div>

      <!-- Tabs -->
      <div class="flex bg-whale-surface rounded-lg p-1 border border-whale-surface/50">
        <button 
          v-for="tab in [{id:1, label:'Wholesale'}, {id:2, label:'Market'}, {id:3, label:'Off Market'}]"
          :key="tab.id"
          @click="activeTab = tab.id"
          class="px-3 py-1.5 text-sm font-medium rounded-md transition-all"
          :class="activeTab === tab.id ? 'bg-ocean-600 text-white shadow-md' : 'text-ocean-300 hover:text-white'"
        >
          {{ tab.label }}
        </button>
      </div>

      <button 
        @click="$router.push('/analyze')" 
        class="bg-ocean-600 hover:bg-ocean-500 text-white px-4 py-2 rounded-lg text-sm font-bold shadow-lg flex items-center gap-2"
      >
        <i class="pi pi-plus"></i> <span class="hidden md:inline">Add Deal</span>
      </button>
    </header>

    <!-- Kanban Board -->
    <div class="flex-1 overflow-x-auto overflow-y-hidden">
      <div class="h-full flex px-4 pb-4 pt-2 md:pt-4 gap-4 min-w-max">
        
        <div 
          v-for="stage in stages" 
          :key="stage.id"
          class="flex flex-col w-[85vw] md:w-80 h-full rounded-xl border backdrop-blur-sm transition-colors"
          :class="stage.color"
        >
          <!-- Column Header -->
          <div class="flex-none p-3 flex justify-between items-center border-b border-white/5">
            <h3 class="font-bold text-ocean-100">{{ stage.name }}</h3>
            <span class="bg-black/20 px-2 py-0.5 rounded-full text-xs font-mono text-ocean-300">
              {{ columns[stage.id]?.length || 0 }}
            </span>
          </div>

          <!-- Draggable Area -->
          <div class="flex-1 overflow-y-auto p-3 scrollbar-hide">
            <VueDraggable
              v-model="columns[stage.id]"
              group="deals"
              @change="(e) => onDrop(e, stage.id)"
              :animation="150"
              class="flex flex-col gap-3 min-h-[100px]"
              ghost-class="opacity-50"
            >
              <div 
                v-for="deal in columns[stage.id]" 
                :key="deal.id"
                @click="openDeal(deal)"
              >
                <DealCard :deal="deal" />
              </div>
            </VueDraggable>
          </div>
        </div>

      </div>
    </div>

    <!-- Detail Modal Placeholder -->
    <div v-if="showDetailModal && selectedDeal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div class="bg-whale-surface w-full max-w-4xl max-h-[90vh] rounded-2xl border border-ocean-500/30 shadow-2xl flex flex-col">
        <div class="flex justify-between items-center p-6 border-b border-white/10">
          <h2 class="text-2xl font-bold text-white">{{ selectedDeal.address }}</h2>
          <button @click="showDetailModal = false" class="text-ocean-300 hover:text-white">
            <i class="pi pi-times text-xl"></i>
          </button>
        </div>
        
        <div class="p-6 overflow-y-auto">
          <p class="text-ocean-200">Full details editing coming soon...</p>
          <div class="grid grid-cols-2 gap-4 mt-4 text-sm text-gray-300">
             <div class="bg-black/20 p-3 rounded">
                <span class="block text-gray-500">Task</span>
                {{ selectedDeal.task || '-' }}
             </div>
             <div class="bg-black/20 p-3 rounded">
                <span class="block text-gray-500">Price</span>
                ${{ selectedDeal.purchasePrice ? selectedDeal.purchasePrice * 1000 : 0 }}
             </div>
             <!-- More fields would go here -->
          </div>
        </div>

        <div class="p-4 border-t border-white/10 flex justify-end">
            <button @click="showDetailModal = false" class="bg-ocean-600 hover:bg-ocean-500 text-white px-6 py-2 rounded-lg">Close</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Custom Scrollbar for columns */
.scrollbar-hide::-webkit-scrollbar {
    display: none;
}
.scrollbar-hide {
    -ms-overflow-style: none;
    scrollbar-width: none;
}
</style>

