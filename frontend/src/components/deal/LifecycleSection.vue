<script setup lang="ts">
/**
 * One box of the deal form: a titled section with the surface-aware frame the four
 * BRRRR lifecycle sections (and the Flip sections) share. Markup lifted verbatim from
 * `DealInputsForm.vue` so the two hosts look exactly as before.
 */
defineProps<{
  title: string;
  /** PrimeIcons name, e.g. "pi-home". */
  icon: string;
  surface: "card" | "panel";
  tone?: "primary" | "warning";
}>();
</script>

<template>
  <section
    v-reveal
    :data-surface="surface"
    class="rounded-card border-ui border-line p-4 shadow-1 md:p-6
           data-[surface=card]:bg-surface data-[surface=panel]:bg-surface-2"
  >
    <UiSectionHeader as="h3" class="mb-4">
      <span class="flex items-center gap-2">
        <span
          class="grid h-7 w-7 place-items-center rounded-ctl"
          :class="tone === 'warning' ? 'bg-warning/12 text-warning' : 'bg-primary/12 text-primary'"
          aria-hidden="true"
        ><i class="pi text-xs" :class="icon"></i></span>
        {{ title }}
      </span>
      <template v-if="$slots.actions" #actions><slot name="actions" /></template>
    </UiSectionHeader>
    <slot />
    <div v-if="$slots.footer" data-part="footer" class="mt-4 grid grid-cols-1 gap-2 md:grid-cols-2">
      <slot name="footer" />
    </div>
  </section>
</template>
