/**
 * A Bought deal's own Google Drive folder (tasks/todo/DealDriveFolderRehabSummaryAndProjection.md): its "Google Drive
 * Link" must be a Drive *folder* link. Mirrors `drive_folder_id_from_link` in `BackEnd/BL/common/deal_drive_folder.py`,
 * which decides; this only explains the problem before the request.
 */
export const GOOGLE_DRIVE_FOLDER_LINK_EXAMPLE = 'https://drive.google.com/drive/folders/…'
const DRIVE_FOLDER_PATH_PATTERN = /^\/drive\/(?:u\/\d+\/)?folders\/[A-Za-z0-9_-]{10,100}\/?$/

/** Null when the link is a Google Drive folder link; otherwise what is wrong with it, in plain words. */
export function googleDriveFolderLinkProblem(link: string | null | undefined): string | null {
  const text = (link ?? '').trim()
  if (!text) return 'Paste the deal\'s Google Drive folder link.'
  let url: URL
  try {
    url = new URL(text)
  } catch {
    return `That is not a link. It looks like ${GOOGLE_DRIVE_FOLDER_LINK_EXAMPLE}`
  }
  if (url.protocol !== 'https:' || url.host !== 'drive.google.com' || url.username || url.password || !DRIVE_FOLDER_PATH_PATTERN.test(url.pathname)) {
    return `That is not a Google Drive folder link (open the folder in Drive and copy its address). It looks like ${GOOGLE_DRIVE_FOLDER_LINK_EXAMPLE}`
  }
  return null
}
