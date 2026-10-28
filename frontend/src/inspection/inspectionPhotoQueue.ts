/**
 * Photos taken while offline (or while Drive is briefly unavailable) wait
 * here until they upload. Blobs are too big for localStorage, so they go in
 * IndexedDB (`bw-inspection-photos`). Where IndexedDB is missing or refused
 * (some private modes) the queue still works, in memory only, for this tab.
 */
export interface QueuedInspectionPhoto {
  queued_photo_id: string;
  inspection_id: string;
  item_key: string;
  full_image: Blob;
  thumbnail_image: Blob;
  queued_at: string;
}

const DATABASE_NAME = "bw-inspection-photos";
const STORE_NAME = "queued_photos";

const inMemoryQueuedPhotos = new Map<string, QueuedInspectionPhoto>();
let openedDatabase: Promise<IDBDatabase | null> | null = null;

function openDatabase(): Promise<IDBDatabase | null> {
  if (openedDatabase) return openedDatabase;
  openedDatabase = new Promise((resolve) => {
    try {
      if (typeof indexedDB === "undefined") return resolve(null);
      const request = indexedDB.open(DATABASE_NAME, 1);
      request.onupgradeneeded = () => request.result.createObjectStore(STORE_NAME, { keyPath: "queued_photo_id" });
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
  return openedDatabase;
}

function runInStore<T>(mode: IDBTransactionMode, action: (store: IDBObjectStore) => IDBRequest<T>): Promise<T | null> {
  return openDatabase().then(
    (database) =>
      new Promise((resolve) => {
        if (!database) return resolve(null);
        try {
          const request = action(database.transaction(STORE_NAME, mode).objectStore(STORE_NAME));
          request.onsuccess = () => resolve(request.result);
          request.onerror = () => resolve(null);
        } catch {
          resolve(null);
        }
      }),
  );
}

export async function queueInspectionPhoto(photo: QueuedInspectionPhoto): Promise<void> {
  inMemoryQueuedPhotos.set(photo.queued_photo_id, photo);
  await runInStore("readwrite", (store) => store.put(photo));
}

export async function queuedPhotosOfInspection(inspectionId: string): Promise<QueuedInspectionPhoto[]> {
  const stored = ((await runInStore("readonly", (store) => store.getAll())) ?? []) as QueuedInspectionPhoto[];
  for (const photo of stored) inMemoryQueuedPhotos.set(photo.queued_photo_id, photo);
  return [...inMemoryQueuedPhotos.values()]
    .filter((photo) => photo.inspection_id === inspectionId)
    .sort((first, second) => first.queued_at.localeCompare(second.queued_at));
}

export async function removeQueuedInspectionPhoto(queuedPhotoId: string): Promise<void> {
  inMemoryQueuedPhotos.delete(queuedPhotoId);
  await runInStore("readwrite", (store) => store.delete(queuedPhotoId));
}
