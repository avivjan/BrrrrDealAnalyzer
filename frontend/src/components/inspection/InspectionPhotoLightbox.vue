<script setup lang="ts">
/** Tap a thumbnail: the full photo, fetched from Drive through the API. */
import { onBeforeUnmount, onMounted, ref } from "vue";

import { fullImageUrlOfPhoto } from "../../inspection/inspectionPhotoUrls";

const props = defineProps<{ inspectionId: string; photoId: string; alt: string; canDelete: boolean }>();
const emit = defineEmits<{ close: []; delete: [] }>();

const fullImageUrl = ref<string | null>(null);
const loadFailed = ref(false);

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Escape") emit("close");
}

onMounted(async () => {
  window.addEventListener("keydown", onKeydown);
  try {
    fullImageUrl.value = await fullImageUrlOfPhoto(props.inspectionId, props.photoId);
  } catch {
    loadFailed.value = true;
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", onKeydown);
  if (fullImageUrl.value) URL.revokeObjectURL(fullImageUrl.value);
});
</script>

<template>
  <Teleport to="body">
    <div
      role="dialog"
      aria-modal="true"
      :aria-label="alt"
      data-testid="inspection.lightbox"
      class="inspection-fade-in fixed inset-0 z-[900] flex flex-col bg-black/90 pb-safe-b pt-safe-t"
      @click.self="emit('close')"
    >
      <div class="flex items-center justify-between gap-2 p-3">
        <button v-if="canDelete" type="button" data-testid="inspection.lightbox.delete" class="min-h-12 rounded-ctl px-4 text-base text-white/90 hover:bg-white/10" @click="emit('delete')">
          <i class="pi pi-trash mr-2" aria-hidden="true"></i>Delete
        </button>
        <span v-else></span>
        <button type="button" data-testid="inspection.lightbox.close" aria-label="Close photo" class="grid size-12 place-items-center rounded-full text-xl text-white hover:bg-white/10" @click="emit('close')">
          <i class="pi pi-times" aria-hidden="true"></i>
        </button>
      </div>
      <div class="flex min-h-0 flex-1 items-center justify-center p-3" @click.self="emit('close')">
        <img v-if="fullImageUrl" :src="fullImageUrl" :alt="alt" class="max-h-full max-w-full rounded-card object-contain" />
        <p v-else-if="loadFailed" class="text-white/80">The full photo could not be loaded right now.</p>
        <i v-else class="pi pi-spinner pi-spin text-3xl text-white/80" aria-hidden="true"></i>
      </div>
    </div>
  </Teleport>
</template>
