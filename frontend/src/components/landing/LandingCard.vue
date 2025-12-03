<template>
  <button
    class="card-surface group relative flex h-48 w-full items-center justify-between overflow-hidden rounded-2xl p-6 text-left transition transform hover:scale-105"
    @click="handleClick"
  >
    <div class="flex flex-col gap-2">
      <div class="flex items-center gap-2 text-ocean-900">
        <span class="text-xl" :class="icon"></span>
        <p class="text-lg font-semibold">{{ title }}</p>
      </div>
      <p class="text-sm text-slate-300">{{ description }}</p>
    </div>
    <div class="absolute inset-0 bg-gradient-to-br from-ocean-600/20 to-ocean-400/10 opacity-0 transition group-hover:opacity-100" />
    <div class="text-ocean-900 text-4xl transition-transform group-hover:translate-x-2">→</div>
  </button>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';

interface Props {
  title: string;
  description: string;
  icon: string;
  href?: string;
  route?: string;
}

const props = defineProps<Props>();
const router = useRouter();

function handleClick() {
  if (props.href) {
    window.open(props.href, '_blank');
    return;
  }
  if (props.route) {
    router.push(props.route);
  }
}
</script>
