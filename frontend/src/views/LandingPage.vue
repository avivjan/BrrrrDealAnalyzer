<template>
  <section class="grid gap-6 md:grid-cols-2 lg:grid-cols-2">
    <LandingCard
      title="Daily Tasks"
      description="Open your mission control checklist"
      icon="pi pi-list-check"
      href="https://docs.google.com/document/d/1xW8KKv-mrJlHxcFwuibhVr685R_CE7BhkJcIECHiI8k/edit?tab=t.0"
    />
    <LandingCard
      title="Airtable"
      description="Jump straight into the live base"
      icon="pi pi-database"
      href="https://airtable.com/appmO7pNFJE06E9E0/pagE3Tz2sIMugDfUP"
    />
    <LandingCard
      title="Analyze Deal"
      description="High-speed BRRRR calculator"
      icon="pi pi-calculator"
      route="/analyze"
    />
    <LandingCard
      title="My Deals"
      description="Kanban, drag, drop, dominate"
      icon="pi pi-th-large"
      route="/my-deals"
    />
  </section>
</template>

<script setup lang="ts">
import LandingCard from '../components/landing/LandingCard.vue';
</script>
