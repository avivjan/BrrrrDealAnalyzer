/**
 * Big Whales Deal Analyzer: save a Bought deal's files into that deal's own Google Drive folder.
 *
 * Runs as a Google Apps Script web app owned by the owner's personal Google
 * account. The web service (BL/common/deal_drive_folder.py) POSTs a file here
 * with the deal folder's id (from the deal's "Google Drive Link"):
 *   - the rehab summary (a .pdf and a .csv) goes into "<deal folder>/Rehab";
 *   - "HTML to Drive" puts "<date> deal projection.html" in the deal folder itself.
 * It writes only into a folder this account owns, only into that folder or its
 * "Rehab" subfolder, and only .pdf, .csv and .html files. It never reads, lists
 * or deletes anything.
 *
 * Every request must carry an HMAC-SHA256 signature made with the shared
 * secret, over "<timestamp>\n<folder id>/<subfolder>/<file name>\n<SHA-256 of the file>",
 * and a timestamp less than 5 minutes old. Anything else is refused, so the web
 * app URL alone lets nobody write to the Drive.
 *
 * Set up (once):
 *   1. Signed in as the owner's personal Google account, open https://script.google.com
 *      and create a new project (e.g. "Deal folders"). Paste this whole file
 *      over the default code.
 *   2. Project Settings (gear) > Script Properties > Add property:
 *        DEAL_DRIVE_FOLDERS_UPLOAD_SECRET = the same secret as on Render.
 *   3. Deploy > New deployment > type "Web app":
 *        Execute as: Me
 *        Who has access: Anyone
 *      Authorize when asked (Advanced > Go to project). Copy the web app URL
 *      (it ends in /exec): it becomes DEAL_DRIVE_FOLDERS_UPLOAD_URL on Render.
 *   4. After changing this file: paste it over the old code, then Deploy > Manage
 *      deployments > Edit > Version: New version > Deploy. The URL and the secret stay.
 */

var LARGEST_TIMESTAMP_AGE_SECONDS = 300;
var LARGEST_FILE_BYTES = 20 * 1024 * 1024;
// The only subfolders a file may go into ('' = the deal folder itself).
var ALLOWED_SUBFOLDER_NAMES = ['', 'Rehab'];
// What may be saved: the file extension and its type.
var SAVED_FILE_KINDS = {
  '.pdf': 'application/pdf',
  '.csv': 'text/csv',
  '.html': 'text/html'
};
var FOLDER_ID_PATTERN = /^[A-Za-z0-9_-]{10,100}$/;

function doPost(e) {
  try {
    var request = JSON.parse(e.postData.contents);
    var secret = PropertiesService.getScriptProperties().getProperty('DEAL_DRIVE_FOLDERS_UPLOAD_SECRET');
    if (!secret) {
      return answer_({ ok: false, error: 'the script has no DEAL_DRIVE_FOLDERS_UPLOAD_SECRET' });
    }
    var nowSeconds = Math.floor(Date.now() / 1000);
    if (typeof request.timestamp !== 'number' || Math.abs(nowSeconds - request.timestamp) > LARGEST_TIMESTAMP_AGE_SECONDS) {
      return answer_({ ok: false, error: 'the request is too old' });
    }
    var subject = request.folder_id + '/' + request.subfolder_name + '/' + request.file_name;
    var signedMessage = request.timestamp + '\n' + subject + '\n' + request.file_sha256;
    var expectedSignature = toHex_(Utilities.computeHmacSha256Signature(signedMessage, secret, Utilities.Charset.UTF_8));
    if (!equalInConstantTime_(expectedSignature, String(request.signature || ''))) {
      return answer_({ ok: false, error: 'wrong signature' });
    }
    if (!FOLDER_ID_PATTERN.test(String(request.folder_id || ''))) {
      return answer_({ ok: false, error: 'not a folder id' });
    }
    if (ALLOWED_SUBFOLDER_NAMES.indexOf(request.subfolder_name) === -1) {
      return answer_({ ok: false, error: 'that subfolder is not allowed' });
    }
    var fileName = String(request.file_name || '').replace(/[\\\/:*?"<>|]/g, '-').replace(/^\.+/, '').slice(0, 200);
    var extension = fileName.slice(fileName.lastIndexOf('.')).toLowerCase();
    if (!SAVED_FILE_KINDS.hasOwnProperty(extension)) {
      return answer_({ ok: false, error: 'only .pdf, .csv and .html files are saved' });
    }
    var fileBytes = Utilities.base64Decode(request.file_base64);
    if (fileBytes.length > LARGEST_FILE_BYTES) {
      return answer_({ ok: false, error: 'the file is too large' });
    }
    if (toHex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, fileBytes)) !== request.file_sha256) {
      return answer_({ ok: false, error: 'the file does not match its SHA-256' });
    }
    var dealFolder;
    try {
      dealFolder = DriveApp.getFolderById(request.folder_id);
    } catch (notFound) {
      return answer_({ ok: false, error: 'the deal folder was not found' });
    }
    if (dealFolder.isTrashed()) {
      return answer_({ ok: false, error: 'the deal folder is in the trash' });
    }
    if (dealFolder.getOwner().getEmail() !== Session.getEffectiveUser().getEmail()) {
      return answer_({ ok: false, error: 'the deal folder is not owned by this account' });
    }
    var targetFolder = request.subfolder_name ? childFolder_(dealFolder, request.subfolder_name) : dealFolder;
    var file = targetFolder.createFile(Utilities.newBlob(fileBytes, SAVED_FILE_KINDS[extension], fileName));
    return answer_({ ok: true, file_id: file.getId(), folder_url: targetFolder.getUrl() });
  } catch (error) {
    return answer_({ ok: false, error: String(error).slice(0, 200) });
  }
}

function childFolder_(parentFolder, folderName) {
  var folders = parentFolder.getFoldersByName(folderName);
  return folders.hasNext() ? folders.next() : parentFolder.createFolder(folderName);
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
