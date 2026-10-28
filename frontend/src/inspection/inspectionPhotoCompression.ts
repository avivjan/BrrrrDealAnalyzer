/**
 * Camera photos are shrunk on the device before upload: a full JPEG of at
 * most 1600 px on its long side (quality 0.8) and a 320 px thumbnail. A
 * 12-megapixel iPad photo drops from ~4 MB to ~300 KB, which matters on a
 * weak signal. Re-encoding through a canvas also drops the EXIF metadata,
 * GPS position included, before anything leaves the device.
 */
export const FULL_PHOTO_LONGEST_SIDE_PIXELS = 1600;
export const THUMBNAIL_LONGEST_SIDE_PIXELS = 320;
export const FULL_PHOTO_JPEG_QUALITY = 0.8;
export const THUMBNAIL_JPEG_QUALITY = 0.7;

export interface CompressedInspectionPhoto {
  fullImage: Blob;
  thumbnailImage: Blob;
}

/** Width and height that fit inside `longestSide`, never upscaling. */
export function scaledDimensions(width: number, height: number, longestSide: number): { width: number; height: number } {
  const scale = Math.min(1, longestSide / Math.max(width, height));
  return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) };
}

async function decodeImage(file: Blob): Promise<{ source: CanvasImageSource; width: number; height: number; release: () => void }> {
  if (typeof createImageBitmap === "function") {
    // `from-image` applies the EXIF orientation, so portrait photos stay upright.
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    return { source: bitmap, width: bitmap.width, height: bitmap.height, release: () => bitmap.close() };
  }
  const url = URL.createObjectURL(file);
  const image = new Image();
  image.src = url;
  await image.decode();
  return { source: image, width: image.naturalWidth, height: image.naturalHeight, release: () => URL.revokeObjectURL(url) };
}

function encodeJpeg(source: CanvasImageSource, width: number, height: number, quality: number): Promise<Blob> {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) return Promise.reject(new Error("This browser cannot process photos."));
  context.drawImage(source, 0, 0, width, height);
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("The photo could not be compressed."))), "image/jpeg", quality);
  });
}

export async function compressInspectionPhoto(file: Blob): Promise<CompressedInspectionPhoto> {
  const decoded = await decodeImage(file);
  try {
    const full = scaledDimensions(decoded.width, decoded.height, FULL_PHOTO_LONGEST_SIDE_PIXELS);
    const thumbnail = scaledDimensions(decoded.width, decoded.height, THUMBNAIL_LONGEST_SIDE_PIXELS);
    const fullImage = await encodeJpeg(decoded.source, full.width, full.height, FULL_PHOTO_JPEG_QUALITY);
    const thumbnailImage = await encodeJpeg(decoded.source, thumbnail.width, thumbnail.height, THUMBNAIL_JPEG_QUALITY);
    return { fullImage, thumbnailImage };
  } finally {
    decoded.release();
  }
}
