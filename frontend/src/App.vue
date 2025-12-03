<template>
  <div class="min-h-screen text-slate-100">
    <header class="sticky top-0 z-40 backdrop-blur bg-ocean-50/80 border-b border-ocean-400/20">
      <div class="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <div class="flex items-center gap-2 font-semibold tracking-wide text-ocean-900">
          <span class="text-xl">BRRRR</span>
          <span class="text-sm text-slate-300">Deal Analyzer</span>
        </div>
        <nav class="flex gap-4 text-sm uppercase tracking-[0.15em] text-slate-300">
          <RouterLink class="hover:text-ocean-900 transition" to="/">Landing</RouterLink>
          <RouterLink class="hover:text-ocean-900 transition" to="/analyze">Analyze</RouterLink>
          <RouterLink class="hover:text-ocean-900 transition" to="/my-deals">My Deals</RouterLink>
        </nav>
      </div>
    </header>
    <main class="mx-auto max-w-6xl px-6 py-10">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts"></script>
