<script setup lang="ts">
import { onMounted, ref } from "vue";
import SendOfferModal from "../components/SendOfferModal.vue";

console.log("View: LandingPage setup");

const isOfferModalOpen = ref(false);

onMounted(() => {
  console.log("View: LandingPage mounted");
});

const cards = [
  {
    title: "Daily Tasks",
    icon: "pi pi-check-square",
    action: "external",
    url: "https://docs.google.com/document/d/1xW8KKv-mrJlHxcFwuibhVr685R_CE7BhkJcIECHiI8k/edit?tab=t.0",
    color: "bg-gradient-to-br from-emerald-500 to-teal-600",
  },
  {
    title: "Airtable",
    icon: "pi pi-database",
    action: "external",
    url: "https://airtable.com/appmO7pNFJE06E9E0/pagE3Tz2sIMugDfUP",
    color: "bg-gradient-to-br from-yellow-500 to-orange-600",
  },
  {
    title: "Analyze Deal",
    icon: "pi pi-calculator",
    action: "internal",
    route: "/analyze",
    color: "bg-gradient-to-br from-blue-500 to-indigo-600",
  },
  {
    title: "My Deals",
    icon: "pi pi-trello", // Using Trello/Kanban icon
    action: "internal",
    route: "/my-deals",
    color: "bg-gradient-to-br from-purple-500 to-fuchsia-600",
  },
];

const openLink = (card: any) => {
  console.log("View: LandingPage - Opening link:", card.title, card.url);
  if (card.action === "external") {
    window.open(card.url, "_blank");
  }
  // Internal navigation is handled by RouterLink logic in template
};
</script>

<template>
  <div
    class="min-h-screen flex items-center justify-center p-6 bg-gray-50 relative overflow-hidden"
  >
    <!-- Background Decor -->
    <div
      class="absolute top-0 left-0 w-full h-full pointer-events-none opacity-30"
    >
      <div
        class="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] bg-blue-200 rounded-full blur-[128px]"
      ></div>
      <div
        class="absolute bottom-[-10%] right-[-10%] w-[500px] h-[500px] bg-purple-200 rounded-full blur-[128px]"
      ></div>
    </div>

    <div class="relative z-10 max-w-6xl w-full">
      <h1
        class="text-4xl md:text-6xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600 text-center mb-6 tracking-tight drop-shadow-sm"
      >
        Big Whales Deal Analyzer
      </h1>

      <div class="flex justify-center mb-10">
        <button
          @click="isOfferModalOpen = true"
          class="px-6 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-full shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-300 font-medium flex items-center gap-2 text-sm md:text-base"
        >
          <i class="pi pi-send"></i>
          Send Market Offer
        </button>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
        <template v-for="card in cards" :key="card.title">
          <component
            :is="card.action === 'internal' ? 'RouterLink' : 'div'"
            :to="card.action === 'internal' ? card.route : undefined"
            @click="card.action === 'external' ? openLink(card) : null"
            class="group relative block cursor-pointer"
          >
            <div
              class="h-64 rounded-2xl p-1 shadow-lg hover:shadow-xl transition-all duration-300 transform group-hover:scale-105 border border-gray-200 overflow-hidden"
              :class="card.color"
            >
              <div
                class="absolute inset-0 bg-white/20 group-hover:bg-transparent transition-colors duration-300"
              ></div>

              <div
                class="relative h-full w-full bg-white/95 backdrop-blur-sm rounded-xl flex flex-col items-center justify-center p-6 border border-white/50"
              >
                <i
                  :class="[
                    card.icon,
                    'text-6xl mb-4 text-gray-700 drop-shadow-sm group-hover:scale-110 transition-transform duration-300 group-hover:text-blue-600',
                  ]"
                ></i>
                <h2
                  class="text-2xl font-bold text-gray-800 tracking-wide group-hover:text-blue-600 transition-colors"
                >
                  {{ card.title }}
                </h2>
              </div>
            </div>
          </component>
        </template>
      </div>
    </div>
    
    <SendOfferModal :isOpen="isOfferModalOpen" @close="isOfferModalOpen = false" />
  </div>
</template>


