<script setup lang="ts">
/**
 * An item's photos: a big camera button (labelled with the item's prompt,
 * e.g. "Photograph the data plate"), the uploaded thumbnails, and photos
 * still waiting to upload (shown from the device, with a clock badge).
 * Tap a thumbnail to enlarge it; delete from the enlarged view.
 */
import { computed, onBeforeUnmount, ref, watch } from "vue";

import { useInspectionStore } from "../../stores/inspectionStore";
import InspectionPhotoLightbox from "./InspectionPhotoLightbox.vue";
import InspectionPhotoThumbnail from "./InspectionPhotoThumbnail.vue";

const props = defineProps<{ itemKey: string; itemLabel: string; photoPrompt?: string }>();

const store = useInspectionStore();
const cameraInput = ref<HTMLInputElement | null>(null);
const isCompressing = ref(false);
const photoErrorMessage = ref<string | null>(null);
const enlargedPhotoId = ref<string | null>(null);

const uploadedPhotos = computed(() => store.photos.filter((photo) => photo.item_key === props.itemKey));
const waitingPhotos = computed(() => store.queuedPhotos.filter((photo) => photo.item_key === props.itemKey));

// Local previews of the photos still waiting to upload.
const waitingPhotoPreviewUrls = ref<Record<string, string>>({});
watch(
  waitingPhotos,
  (photos) => {
    const next: Record<string, string> = {};
    for (const photo of photos) next[photo.queued_photo_id] = waitingPhotoPreviewUrls.value[photo.queued_photo_id] ?? URL.createObjectURL(photo.thumbnail_image);
    for (const [queuedPhotoId, url] of Object.entries(waitingPhotoPreviewUrls.value)) if (!next[queuedPhotoId]) URL.revokeObjectURL(url);
    waitingPhotoPreviewUrls.value = next;
  },
  { immediate: true },
);
onBeforeUnmount(() => Object.values(waitingPhotoPreviewUrls.value).forEach((url) => URL.revokeObjectURL(url)));

async function onPhotosTaken(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = [...(input.files ?? [])];
  input.value = "";
  photoErrorMessage.value = null;
  isCompressing.value = true;
  try {
    for (const file of files) await store.addPhoto(props.itemKey, file);
  } catch {
    photoErrorMessage.value = "That photo could not be read. Try taking it again.";
  } finally {
    isCompressing.value = false;
  }
}

async function deleteEnlargedPhoto() {
  if (!enlargedPhotoId.value) return;
  const photoId = enlargedPhotoId.value;
  enlargedPhotoId.value = null;
  try {
    await store.deletePhoto(photoId);
  } catch {
    photoErrorMessage.value = "The photo could not be deleted. Check the connection.";
  }
}
</script>

<template>
  <div>
    <input ref="cameraInput" type="file" accept="image/*" capture="environment" multiple class="sr-only" data-testid="inspection.photos.input" tabindex="-1" aria-hidden="true" @change="onPhotosTaken" />
    <div class="flex flex-wrap items-center gap-3">
      <button
        type="button"
        data-testid="inspection.photos.camera"
        class="inspection-press flex min-h-16 items-center gap-3 rounded-card border-2 border-dashed border-primary/60 bg-primary/5 px-5 text-base font-semibold text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        :disabled="isCompressing"
        @click="cameraInput?.click()"
      >
        <i :class="isCompressing ? 'pi pi-spinner pi-spin' : 'pi pi-camera'" class="text-xl text-primary" aria-hidden="true"></i>
        {{ photoPrompt || "Take a photo" }}
      </button>
      <ul role="list" class="flex flex-wrap gap-2">
        <li v-for="photo in uploadedPhotos" :key="photo.id">
          <button type="button" :data-testid="`inspection.photos.thumbnail.${photo.id}`" :aria-label="`Enlarge photo of ${itemLabel}`" class="block size-16 overflow-hidden rounded-ctl border border-line focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" @click="enlargedPhotoId = photo.id">
            <InspectionPhotoThumbnail :inspection-id="store.inspection!.id" :photo-id="photo.id" :alt="`Photo of ${itemLabel}`" />
          </button>
        </li>
        <li v-for="photo in waitingPhotos" :key="photo.queued_photo_id" class="relative">
          <img :src="waitingPhotoPreviewUrls[photo.queued_photo_id]" :alt="`Photo of ${itemLabel}, waiting to upload`" class="size-16 rounded-ctl border border-line object-cover opacity-70" />
          <span class="absolute bottom-1 right-1 grid size-5 place-items-center rounded-full bg-surface text-[10px] text-fg-muted shadow-1" title="Waiting to upload">
            <i class="pi pi-clock" aria-hidden="true"></i>
          </span>
          <button type="button" :aria-label="`Discard photo of ${itemLabel} waiting to upload`" class="absolute -right-2 -top-2 grid size-7 place-items-center rounded-full bg-surface text-xs text-fg shadow-2" @click="store.discardQueuedPhoto(photo.queued_photo_id)">
            <i class="pi pi-times" aria-hidden="true"></i>
          </button>
        </li>
      </ul>
    </div>
    <p v-if="photoErrorMessage" role="alert" class="mt-2 text-sm text-negative">{{ photoErrorMessage }}</p>
    <InspectionPhotoLightbox
      v-if="enlargedPhotoId && store.inspection"
      :inspection-id="store.inspection.id"
      :photo-id="enlargedPhotoId"
      :alt="`Photo of ${itemLabel}`"
      :can-delete="true"
      @close="enlargedPhotoId = null"
      @delete="deleteEnlargedPhoto"
    />
  </div>
</template>
