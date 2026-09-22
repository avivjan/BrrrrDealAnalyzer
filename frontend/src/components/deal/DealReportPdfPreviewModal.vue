<script setup lang="ts">
/**
 * The in-app preview of the branded deal report: the PDF in an iframe, a Download
 * button, a close button. Shared by the My Deals and Bought Deals modals; the host
 * owns the state through `useDealReportPdf` and passes the preview in.
 *
 * `modalEnterOnly` — the same opening, no leave hook at all, so the overlay is gone
 * from the DOM the instant the app says it is closed. The panel is a raw `div`
 * rather than a `UiModalPanel`, so the preset finds no `[data-ui="modal-panel"]`
 * and the overlay simply fades: no transform touches a `position: fixed` box.
 *
 * `testIdPrefix` keeps each host's existing test ids (`mydeals.pdf-modal…`).
 */
import type { DealReportPdfPreview } from "../../composables/useDealReportPdf";

defineProps<{
  preview: DealReportPdfPreview | null;
  /** `mydeals` or `boughtdeals`: the host's test-id namespace. */
  testIdPrefix: string;
}>();

defineEmits<{
  (e: "download"): void;
  (e: "close"): void;
}>();
</script>

<template>
  <UiTransition preset="modalEnterOnly" appear>
    <div
      v-if="preview"
      :data-testid="`${testIdPrefix}.pdf-modal`"
      class="fixed inset-0 bg-fg/60 md:backdrop-blur-sm z-[60] flex items-center justify-center p-4"
      @click.self="$emit('close')"
    >
      <!--
        `pb-safe-b` on the panel, not on a bar inside it: the last box here is the
        PDF `<iframe>`, and a 92svh dialog centred on a phone bottoms out inside
        the home-indicator band. The inset is 0 on a device without one.
      -->
      <div class="bg-surface w-full max-w-5xl h-[92svh] pb-safe-b rounded-panel border border-line shadow-3 flex flex-col overflow-hidden">
        <div class="flex justify-between items-center gap-3 px-5 py-3 border-b border-line shrink-0">
          <div class="flex items-center gap-3 min-w-0">
            <UiBadge class="shrink-0 font-bold uppercase tracking-wide" :deal-type="preview.dealType">
              {{ preview.dealType }}
            </UiBadge>
            <div class="min-w-0">
              <h3 class="text-sm font-bold text-fg truncate">{{ preview.title }}</h3>
              <p class="text-[11px] text-fg-muted">Deal Report Preview &middot; Big Whales</p>
            </div>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <UiButton
              :data-testid="`${testIdPrefix}.pdf-modal.download`"
              variant="secondary"
              size="sm"
              class="min-h-9 touch:min-h-11 border-positive/30 bg-positive/10 text-positive hover:bg-positive/20"
              title="Download this PDF"
              @click="$emit('download')"
            >
              <i class="pi pi-download text-base" aria-hidden="true"></i>
              <span class="hidden sm:inline">Download</span>
            </UiButton>
            <UiIconButton
              :data-testid="`${testIdPrefix}.pdf-modal.close`"
              label="Close preview"
              title="Close preview"
              @click="$emit('close')"
            >
              <i class="pi pi-times text-lg" aria-hidden="true"></i>
            </UiIconButton>
          </div>
        </div>
        <iframe
          :data-testid="`${testIdPrefix}.pdf-modal.iframe`"
          :src="preview.url"
          class="flex-1 w-full bg-surface-2"
          title="Deal Report PDF"
        ></iframe>
      </div>
    </div>
  </UiTransition>
</template>
