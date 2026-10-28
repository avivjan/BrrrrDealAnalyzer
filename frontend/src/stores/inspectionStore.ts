import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { inspectionApi } from "../api/inspection";
import type { InspectionItemAnswers } from "../inspection/inspectionChecklistLogic";
import {
  mergePendingItemChange,
  pendingChangeAfterSent,
  readPendingItemChanges,
  writePendingItemChanges,
  type PendingItemChangesByItemKey,
} from "../inspection/inspectionOfflineQueue";
import { compressInspectionPhoto } from "../inspection/inspectionPhotoCompression";
import { queueInspectionPhoto, queuedPhotosOfInspection, removeQueuedInspectionPhoto, type QueuedInspectionPhoto } from "../inspection/inspectionPhotoQueue";
import { rememberInspectionOnDevice } from "../inspection/inspectionRecentOnDevice";
import type { InspectionItemUpdateReq, InspectionPhotoRes, PublicInspectionRes } from "../types/inspection";

/**
 * One open inspection walkthrough.
 *
 * Every edit is applied on screen at once, merged into a per-item pending
 * change kept on this device (`inspectionOfflineQueue.ts`), and sent after a
 * short pause as a PATCH of that one item, never the whole document, so two
 * people filling the same inspection don't overwrite each other. A failed
 * send stays queued and is retried when the browser comes back online and
 * every 15 s. A poll every 10 s shows the other person's changes, except on
 * items this device is still saving.
 */
export type InspectionSaveState = "idle" | "saving" | "saved" | "offline" | "error";

export const ITEM_SAVE_DEBOUNCE_MILLISECONDS = 600;
export const PENDING_CHANGES_RETRY_MILLISECONDS = 15_000;
export const OTHER_DEVICE_CHANGES_POLL_MILLISECONDS = 10_000;

function isNetworkError(error: any): boolean {
  return !error?.response;
}

function answersFromInspection(inspection: PublicInspectionRes): Record<string, InspectionItemAnswers> {
  return Object.fromEntries(
    inspection.items.map((item) => [item.item_key, { item_status: item.item_status, item_notes: item.item_notes, item_field_values: { ...item.item_field_values } }]),
  );
}

function applyChangeToAnswers(answers: InspectionItemAnswers | undefined, change: InspectionItemUpdateReq): InspectionItemAnswers {
  const next: InspectionItemAnswers = {
    item_status: answers?.item_status ?? "not_checked",
    item_notes: answers?.item_notes ?? null,
    item_field_values: { ...(answers?.item_field_values ?? {}) },
  };
  if (change.item_status !== undefined) next.item_status = change.item_status;
  if (change.item_notes !== undefined) next.item_notes = change.item_notes || null;
  for (const [fieldKey, value] of Object.entries(change.item_field_values ?? {})) {
    if (value === null) delete next.item_field_values[fieldKey];
    else next.item_field_values[fieldKey] = value;
  }
  return next;
}

export const useInspectionStore = defineStore("inspection", () => {
  const inspection = ref<PublicInspectionRes | null>(null);
  const answersByItemKey = ref<Record<string, InspectionItemAnswers>>({});
  const photos = ref<InspectionPhotoRes[]>([]);
  const queuedPhotos = ref<QueuedInspectionPhoto[]>([]);
  const pendingChanges = ref<PendingItemChangesByItemKey>({});
  const isLoading = ref(false);
  const loadErrorMessage = ref<string | null>(null);
  const saveState = ref<InspectionSaveState>("idle");
  const saveErrorMessage = ref<string | null>(null);

  const pendingChangeCount = computed(() => Object.keys(pendingChanges.value).length + queuedPhotos.value.length);

  const debounceTimersByItemKey = new Map<string, ReturnType<typeof setTimeout>>();
  let retryTimer: ReturnType<typeof setInterval> | null = null;
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let isFlushing = false;
  let savedStateResetTimer: ReturnType<typeof setTimeout> | null = null;

  const inspectionId = () => inspection.value?.id ?? null;

  function persistPendingChanges() {
    const id = inspectionId();
    if (id) writePendingItemChanges(id, pendingChanges.value);
  }

  function applyServerInspection(serverInspection: PublicInspectionRes) {
    inspection.value = serverInspection;
    photos.value = serverInspection.photos;
    const serverAnswers = answersFromInspection(serverInspection);
    // Items this device is still saving keep the local answers on top of the server's.
    for (const [itemKey, change] of Object.entries(pendingChanges.value)) {
      serverAnswers[itemKey] = applyChangeToAnswers(serverAnswers[itemKey], change);
    }
    answersByItemKey.value = serverAnswers;
  }

  function markSaved() {
    if (pendingChangeCount.value > 0) return;
    saveState.value = "saved";
    if (savedStateResetTimer) clearTimeout(savedStateResetTimer);
    savedStateResetTimer = setTimeout(() => {
      if (saveState.value === "saved") saveState.value = "idle";
    }, 2000);
  }

  async function loadInspection(id: string) {
    stopSyncing();
    isLoading.value = true;
    loadErrorMessage.value = null;
    pendingChanges.value = readPendingItemChanges(id);
    try {
      applyServerInspection(await inspectionApi.getInspection(id));
      rememberInspectionOnDevice({
        inspection_id: id,
        property_address: inspection.value!.property_address,
        inspection_date: inspection.value!.inspection_date,
      });
      queuedPhotos.value = await queuedPhotosOfInspection(id);
      startSyncing();
      if (pendingChangeCount.value > 0) void flushPendingChanges();
    } catch (error: any) {
      inspection.value = null;
      loadErrorMessage.value =
        error?.response?.status === 404 ? "This inspection does not exist, or the link is incomplete." : "The inspection could not be loaded. Check the connection and try again.";
    } finally {
      isLoading.value = false;
    }
  }

  /** Apply an edit on screen now and save it shortly. */
  function changeItem(itemKey: string, change: InspectionItemUpdateReq) {
    answersByItemKey.value = { ...answersByItemKey.value, [itemKey]: applyChangeToAnswers(answersByItemKey.value[itemKey], change) };
    pendingChanges.value = { ...pendingChanges.value, [itemKey]: mergePendingItemChange(pendingChanges.value[itemKey], change) };
    persistPendingChanges();
    saveState.value = "saving";
    const existingTimer = debounceTimersByItemKey.get(itemKey);
    if (existingTimer) clearTimeout(existingTimer);
    debounceTimersByItemKey.set(
      itemKey,
      setTimeout(() => {
        debounceTimersByItemKey.delete(itemKey);
        void flushPendingChanges();
      }, ITEM_SAVE_DEBOUNCE_MILLISECONDS),
    );
  }

  async function flushPendingChanges() {
    const id = inspectionId();
    if (!id || isFlushing) return;
    isFlushing = true;
    let wentOffline = false;
    try {
      for (const [itemKey, sentChange] of Object.entries(pendingChanges.value)) {
        if (debounceTimersByItemKey.has(itemKey)) continue; // still being typed: its own timer sends it
        saveState.value = "saving";
        try {
          await inspectionApi.updateInspectionItem(id, itemKey, sentChange);
          const remaining = pendingChangeAfterSent(pendingChanges.value[itemKey], sentChange);
          const next = { ...pendingChanges.value };
          if (remaining) next[itemKey] = remaining;
          else delete next[itemKey];
          pendingChanges.value = next;
          persistPendingChanges();
        } catch (error: any) {
          if (isNetworkError(error) || error?.response?.status === 429 || error?.response?.status >= 500) {
            wentOffline = true;
            break;
          }
          // The server refused this change (it is invalid): drop it rather than retry forever.
          const next = { ...pendingChanges.value };
          delete next[itemKey];
          pendingChanges.value = next;
          persistPendingChanges();
          saveState.value = "error";
          saveErrorMessage.value = typeof error?.response?.data?.detail === "string" ? error.response.data.detail : "A change could not be saved.";
          return;
        }
      }
      if (!wentOffline) wentOffline = !(await uploadQueuedPhotos());
    } finally {
      isFlushing = false;
    }
    if (wentOffline) saveState.value = "offline";
    else markSaved();
  }

  /** Returns false when the photos could not all be sent (no signal, or Drive unavailable). */
  async function uploadQueuedPhotos(): Promise<boolean> {
    const id = inspectionId();
    if (!id) return true;
    for (const queuedPhoto of [...queuedPhotos.value]) {
      try {
        const uploaded = await inspectionApi.uploadInspectionPhoto(id, queuedPhoto.item_key, queuedPhoto.full_image, queuedPhoto.thumbnail_image);
        photos.value = [...photos.value, uploaded];
      } catch (error: any) {
        if (isNetworkError(error) || error?.response?.status === 429 || error?.response?.status >= 500) return false;
        saveErrorMessage.value = typeof error?.response?.data?.detail === "string" ? error.response.data.detail : "A photo could not be saved.";
        saveState.value = "error";
      }
      await removeQueuedInspectionPhoto(queuedPhoto.queued_photo_id);
      queuedPhotos.value = queuedPhotos.value.filter((photo) => photo.queued_photo_id !== queuedPhoto.queued_photo_id);
    }
    return true;
  }

  async function addPhoto(itemKey: string, file: File) {
    const id = inspectionId();
    if (!id) return;
    const { fullImage, thumbnailImage } = await compressInspectionPhoto(file);
    const queuedPhoto: QueuedInspectionPhoto = {
      queued_photo_id: crypto.randomUUID(),
      inspection_id: id,
      item_key: itemKey,
      full_image: fullImage,
      thumbnail_image: thumbnailImage,
      queued_at: new Date().toISOString(),
    };
    await queueInspectionPhoto(queuedPhoto);
    queuedPhotos.value = [...queuedPhotos.value, queuedPhoto];
    saveState.value = "saving";
    await flushPendingChanges();
  }

  async function deletePhoto(photoId: string) {
    const id = inspectionId();
    if (!id) return;
    await inspectionApi.deleteInspectionPhoto(id, photoId);
    photos.value = photos.value.filter((photo) => photo.id !== photoId);
  }

  async function discardQueuedPhoto(queuedPhotoId: string) {
    await removeQueuedInspectionPhoto(queuedPhotoId);
    queuedPhotos.value = queuedPhotos.value.filter((photo) => photo.queued_photo_id !== queuedPhotoId);
  }

  async function updateStartInfo(change: { property_address?: string; inspection_date?: string; inspector_name?: string | null }) {
    const id = inspectionId();
    if (!id) return;
    applyServerInspection(await inspectionApi.updateInspectionStartInfo(id, change));
  }

  /** Sends what is pending first, so the server judges the CRITICAL items on the latest answers. */
  async function completeInspection(completionOverrideReason: string | null) {
    const id = inspectionId();
    if (!id) return;
    for (const timer of debounceTimersByItemKey.values()) clearTimeout(timer);
    debounceTimersByItemKey.clear();
    await flushPendingChanges();
    if (Object.keys(pendingChanges.value).length > 0) throw new Error("Some answers are not saved yet. Reconnect, then finish.");
    applyServerInspection(await inspectionApi.completeInspection(id, completionOverrideReason));
  }

  async function pollOtherDeviceChanges() {
    const id = inspectionId();
    if (!id || isFlushing || (typeof document !== "undefined" && document.visibilityState === "hidden")) return;
    try {
      applyServerInspection(await inspectionApi.getInspection(id));
    } catch {
      /* offline: the next poll tries again */
    }
  }

  const onBackOnline = () => void flushPendingChanges();

  function startSyncing() {
    retryTimer = setInterval(() => {
      if (Object.keys(pendingChanges.value).length > 0 || queuedPhotos.value.length > 0) void flushPendingChanges();
    }, PENDING_CHANGES_RETRY_MILLISECONDS);
    pollTimer = setInterval(() => void pollOtherDeviceChanges(), OTHER_DEVICE_CHANGES_POLL_MILLISECONDS);
    if (typeof window !== "undefined") window.addEventListener("online", onBackOnline);
  }

  function stopSyncing() {
    if (retryTimer) clearInterval(retryTimer);
    if (pollTimer) clearInterval(pollTimer);
    retryTimer = null;
    pollTimer = null;
    if (typeof window !== "undefined") window.removeEventListener("online", onBackOnline);
  }

  return {
    inspection,
    answersByItemKey,
    photos,
    queuedPhotos,
    pendingChanges,
    pendingChangeCount,
    isLoading,
    loadErrorMessage,
    saveState,
    saveErrorMessage,
    loadInspection,
    changeItem,
    flushPendingChanges,
    addPhoto,
    deletePhoto,
    discardQueuedPhoto,
    updateStartInfo,
    completeInspection,
    pollOtherDeviceChanges,
    stopSyncing,
  };
});
