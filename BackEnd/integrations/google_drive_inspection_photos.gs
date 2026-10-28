/**
 * Big Whales Deal Analyzer: keep property inspection photos in Google Drive.
 *
 * Runs as a Google Apps Script web app owned by bigwhalesllc@gmail.com. The
 * web service (BL/inspection/common/inspection_photo_google_drive.py) POSTs here to:
 *   save   a JPEG into "property inspections/<inspection folder>", creating the folders
 *   read   a photo back (base64), by Drive file id
 *   trash  a photo, by Drive file id
 * `read` and `trash` only act on files inside the "property inspections" folder tree,
 * so a leaked or forged file id can never reach any other file in this Drive.
 *
 * Every request must carry an HMAC-SHA256 signature made with the shared
 * secret, over "<timestamp>\n<action>\n<subject>\n<SHA-256 of the image, or empty>",
 * and a timestamp less than 5 minutes old. Anything else is refused, so the web
 * app URL alone lets nobody read or write the Drive.
 *
 * Set up (once):
 *   1. Signed in as bigwhalesllc@gmail.com, open https://script.google.com and
 *      create a new project (e.g. "Inspection photos"). Paste this whole file
 *      over the default code.
 *   2. Project Settings (gear) > Script Properties > Add property:
 *        INSPECTION_PHOTOS_DRIVE_UPLOAD_SECRET = the same secret as on Render.
 *   3. Deploy > New deployment > type "Web app":
 *        Execute as: Me (bigwhalesllc@gmail.com)
 *        Who has access: Anyone
 *      Authorize when asked (Advanced > Go to project). Copy the web app URL
 *      (it ends in /exec): it becomes INSPECTION_PHOTOS_DRIVE_UPLOAD_URL on Render.
 */

var LARGEST_TIMESTAMP_AGE_SECONDS = 300;
var PROPERTY_INSPECTIONS_FOLDER_NAME = 'property inspections';
var LARGEST_IMAGE_BYTES = 4 * 1024 * 1024;

function doPost(e) {
  try {
    var request = JSON.parse(e.postData.contents);
    var secret = PropertiesService.getScriptProperties().getProperty('INSPECTION_PHOTOS_DRIVE_UPLOAD_SECRET');
    if (!secret) {
      return answer_({ ok: false, error: 'the script has no INSPECTION_PHOTOS_DRIVE_UPLOAD_SECRET' });
    }
    var nowSeconds = Math.floor(Date.now() / 1000);
    if (typeof request.timestamp !== 'number' || Math.abs(nowSeconds - request.timestamp) > LARGEST_TIMESTAMP_AGE_SECONDS) {
      return answer_({ ok: false, error: 'the request is too old' });
    }
    var signedMessage = request.timestamp + '\n' + request.action + '\n' + request.subject + '\n' + (request.image_sha256 || '');
    var expectedSignature = toHex_(Utilities.computeHmacSha256Signature(signedMessage, secret, Utilities.Charset.UTF_8));
    if (!equalInConstantTime_(expectedSignature, String(request.signature || ''))) {
      return answer_({ ok: false, error: 'wrong signature' });
    }
    if (request.action === 'save') return savePhoto_(request);
    if (request.action === 'read') return readPhoto_(request);
    if (request.action === 'trash') return trashPhoto_(request);
    return answer_({ ok: false, error: 'unknown action' });
  } catch (error) {
    return answer_({ ok: false, error: String(error).slice(0, 200) });
  }
}

function savePhoto_(request) {
  var folderName = safeName_(request.inspection_folder_name);
  var fileName = safeName_(request.file_name);
  if (request.subject !== request.inspection_folder_name + '/' + request.file_name) {
    return answer_({ ok: false, error: 'the subject does not match the folder and file name' });
  }
  if (fileName.slice(-4).toLowerCase() !== '.jpg') {
    return answer_({ ok: false, error: 'only .jpg files are saved' });
  }
  var imageBytes = Utilities.base64Decode(request.image_base64);
  if (imageBytes.length > LARGEST_IMAGE_BYTES) {
    return answer_({ ok: false, error: 'the image is too large' });
  }
  if (toHex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, imageBytes)) !== request.image_sha256) {
    return answer_({ ok: false, error: 'the image does not match its SHA-256' });
  }
  var inspectionFolder = childFolder_(propertyInspectionsFolder_(), folderName);
  var file = inspectionFolder.createFile(Utilities.newBlob(imageBytes, 'image/jpeg', fileName));
  return answer_({ ok: true, file_id: file.getId() });
}

function readPhoto_(request) {
  var file = fileInsidePropertyInspections_(request);
  if (!file) return answer_({ ok: false, error: 'no such photo' });
  return answer_({ ok: true, image_base64: Utilities.base64Encode(file.getBlob().getBytes()) });
}

function trashPhoto_(request) {
  var file = fileInsidePropertyInspections_(request);
  if (!file) return answer_({ ok: true, already_gone: true });
  file.setTrashed(true);
  return answer_({ ok: true });
}

function fileInsidePropertyInspections_(request) {
  if (request.subject !== request.file_id) return null;
  var file;
  try {
    file = DriveApp.getFileById(String(request.file_id));
  } catch (error) {
    return null;
  }
  if (file.isTrashed()) return null;
  var rootId = propertyInspectionsFolder_().getId();
  var parents = file.getParents();
  while (parents.hasNext()) {
    var inspectionFolder = parents.next();
    var grandParents = inspectionFolder.getParents();
    while (grandParents.hasNext()) {
      if (grandParents.next().getId() === rootId) return file;
    }
  }
  return null;
}

function propertyInspectionsFolder_() {
  return childFolder_(DriveApp.getRootFolder(), PROPERTY_INSPECTIONS_FOLDER_NAME);
}

function childFolder_(parent, folderName) {
  var folders = parent.getFoldersByName(folderName);
  return folders.hasNext() ? folders.next() : parent.createFolder(folderName);
}

function safeName_(name) {
  return String(name || 'photo').replace(/[\\\/:*?"<>|]/g, '-').slice(0, 150);
}

function answer_(body) {
  return ContentService.createTextOutput(JSON.stringify(body)).setMimeType(ContentService.MimeType.JSON);
}

function toHex_(bytes) {
  return bytes.map(function (b) { return ('0' + (b & 0xff).toString(16)).slice(-2); }).join('');
}

function equalInConstantTime_(a, b) {
  if (a.length !== b.length) return false;
  var difference = 0;
  for (var i = 0; i < a.length; i++) difference |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return difference === 0;
}
