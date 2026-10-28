import { inspectionApi } from "../api/inspection";

/**
 * `blob:` URLs for inspection photos. The images come through the API with
 * axios (the CSP's img-src does not name the API origin), and each thumbnail
 * is fetched once per page load and shared by the card and the summary.
 */
const thumbnailUrlRequestsByPhotoId = new Map<string, Promise<string>>();

export function thumbnailUrlOfPhoto(inspectionId: string, photoId: string): Promise<string> {
  let request = thumbnailUrlRequestsByPhotoId.get(photoId);
  if (!request) {
    request = inspectionApi.getInspectionPhoto(inspectionId, photoId, "thumbnail").then((blob) => URL.createObjectURL(blob));
    request.catch(() => thumbnailUrlRequestsByPhotoId.delete(photoId));
    thumbnailUrlRequestsByPhotoId.set(photoId, request);
  }
  return request;
}

export async function fullImageUrlOfPhoto(inspectionId: string, photoId: string): Promise<string> {
  return URL.createObjectURL(await inspectionApi.getInspectionPhoto(inspectionId, photoId, "full"));
}
