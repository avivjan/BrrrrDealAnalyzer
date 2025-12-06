<script setup lang="ts">
const cards = [
  {
    title: 'Daily Tasks',
    icon: 'pi pi-check-square',
    action: 'external',
    url: 'https://docs.google.com/document/d/1xW8KKv-mrJlHxcFwuibhVr685R_CE7BhkJcIECHiI8k/edit?tab=t.0',
    color: 'bg-gradient-to-br from-emerald-600 to-teal-800'
  },
  {
    title: 'Airtable',
    icon: 'pi pi-database',
    action: 'external',
    url: 'https://airtable.com/appmO7pNFJE06E9E0/pagE3Tz2sIMugDfUP',
    color: 'bg-gradient-to-br from-yellow-500 to-orange-700'
  },
  {
    title: 'Analyze Deal',
    icon: 'pi pi-calculator',
    action: 'internal',
    route: '/analyze',
    color: 'bg-gradient-to-br from-blue-600 to-indigo-800'
  },
  {
    title: 'My Deals',
    icon: 'pi pi-trello', // Using Trello/Kanban icon
    action: 'internal',
    route: '/my-deals',
    color: 'bg-gradient-to-br from-purple-600 to-fuchsia-800'
  }
];

const openLink = (card: any) => {
  if (card.action === 'external') {
    window.open(card.url, '_blank');
  }
  // Internal navigation is handled by RouterLink logic in template
};
</script>

<template>
  <div class="min-h-screen flex items-center justify-center p-6 bg-whale-dark relative overflow-hidden">
    <!-- Background Decor -->
    <div class="absolute top-0 left-0 w-full h-full pointer-events-none opacity-20">
      <div class="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] bg-ocean-600 rounded-full blur-[128px]"></div>
      <div class="absolute bottom-[-10%] right-[-10%] w-[500px] h-[500px] bg-purple-900 rounded-full blur-[128px]"></div>
    </div>

    <div class="relative z-10 max-w-6xl w-full">
      <h1 class="text-4xl md:text-6xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-ocean-300 to-ocean-100 text-center mb-12 tracking-tight drop-shadow-lg">
        BRRRR Deal Analyzer
      </h1>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
        <template v-for="card in cards" :key="card.title">
          <component 
            :is="card.action === 'internal' ? 'RouterLink' : 'div'"
            :to="card.action === 'internal' ? card.route : undefined"
            @click="card.action === 'external' ? openLink(card) : null"
            class="group relative block cursor-pointer"
          >
            <div 
              class="h-64 rounded-2xl p-1 shadow-xl transition-all duration-300 transform group-hover:scale-105 group-hover:shadow-2xl border border-whale-surface/50 overflow-hidden"
              :class="card.color"
            >
              <div class="absolute inset-0 bg-black/20 group-hover:bg-transparent transition-colors duration-300"></div>
              
              <div class="relative h-full w-full bg-whale-surface/90 backdrop-blur-sm rounded-xl flex flex-col items-center justify-center p-6 border border-white/5">
                <i :class="[card.icon, 'text-6xl mb-4 text-white drop-shadow-md group-hover:scale-110 transition-transform duration-300']"></i>
                <h2 class="text-2xl font-bold text-white tracking-wide group-hover:text-ocean-200 transition-colors">
                  {{ card.title }}
                </h2>
              </div>
            </div>
          </component>
        </template>
      </div>
    </div>
  </div>
</template>

