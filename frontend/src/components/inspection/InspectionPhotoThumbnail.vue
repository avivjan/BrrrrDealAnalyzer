<script setup lang="ts">
/** One uploaded photo's thumbnail; it loads through the API as a blob. */
import { onMounted, ref } from "vue";

import { thumbnailUrlOfPhoto } from "../../inspection/inspectionPhotoUrls";

const props = defineProps<{ inspectionId: string; photoId: string; alt: string }>();
const thumbnailUrl = ref<string | null>(null);
const failedToLoad = ref(false);

onMounted(async () => {
  try {
    thumbnailUrl.value = await thumbnailUrlOfPhoto(props.inspectionId, props.photoId);
  } catch {
    failedToLoad.value = true;
  }
});
</script>

<template>
  <img v-if="thumbnailUrl" :src="thumbnailUrl" :alt="alt" class="size-full object-cover" />
  <span v-else class="grid size-full place-items-center bg-surface-2 text-fg-muted">
    <i :class="failedToLoad ? 'pi pi-image' : 'pi pi-spinner pi-spin'" aria-hidden="true"></i>
  </span>
</template>
