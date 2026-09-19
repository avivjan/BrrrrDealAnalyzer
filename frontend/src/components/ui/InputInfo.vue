<script setup lang="ts">
/**
 * The (i) beside an input: hover, focus or tap to read which outputs the input moves.
 *
 * A real `<button>` so it is reachable by keyboard and by touch (`UiTooltip` opens on
 * focus-within and on tap); `aria-describedby` points at the bubble so a screen reader
 * gets the same text.
 */
import UiTooltip from "./UiTooltip.vue";

defineProps<{
  /** The full tooltip text, e.g. "Affects: Cash to Close (Buy), Cash Needed". */
  content: string;
  /** Accessible name of the button; the field's label is the natural choice. */
  fieldLabel?: string;
}>();
</script>

<template>
  <UiTooltip v-if="content" :content="content" placement="bottom" v-slot="{ describedBy }">
    <button
      type="button"
      data-ui="input-info"
      class="inline-flex h-5 w-5 items-center justify-center rounded-full text-fg-muted hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring touch:min-h-11 touch:min-w-11 touch:-my-3"
      :aria-label="`What ${fieldLabel ?? 'this input'} affects`"
      :aria-describedby="describedBy"
    >
      <i class="pi pi-info-circle text-[13px]" aria-hidden="true"></i>
    </button>
  </UiTooltip>
</template>
