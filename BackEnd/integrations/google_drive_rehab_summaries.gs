/**
 * Big Whales Deal Analyzer: save each rehab summary (a PDF and a CSV) to Google Drive.
 *
 * Runs as a Google Apps Script web app owned by the owner's personal Google
 * account. The web service (BL/liquidity/constructionAccount/rehab_summary_google_drive.py)
 * POSTs each file here when a construction account is closed out; this script
 * saves it in "rehab summaries/<the deal's folder>", creating the folders the
 * first time. It never reads, lists or deletes anything, and writes only inside
 * "rehab summaries".
 *
 * Every request must carry an HMAC-SHA256 signature made with the shared
 * secret, over "<timestamp>\n<folder name>/<file name>\n<SHA-256 of the file>",
 * and a timestamp less than 5 minutes old. Anything else is refused, so the web
 * app URL alone lets nobody write to the Drive.
 *
 * Set up (once):
 *   1. Signed in as the owner's personal Google account, open https://script.google.com
 *      and create a new project (e.g. "Rehab summaries"). Paste this whole file
 *      over the default code.
 *   2. Project Settings (gear) > Script Properties > Add property:
 *        REHAB_SUMMARY_DRIVE_UPLOAD_SECRET = the same secret as on Render.
 *   3. Deploy > New deployment > type "Web app":
 *        Execute as: Me
 *        Who has access: Anyone
 *      Authorize when asked (Advanced > Go to project). Copy the web app URL
 *      (it ends in /exec): it becomes REHAB_SUMMARY_DRIVE_UPLOAD_URL on Render.
 */

var LARGEST_TIMESTAMP_AGE_SECONDS = 300;
var REHAB_SUMMARIES_FOLDER_NAME = 'rehab summaries';
var LARGEST_FILE_BYTES = 20 * 1024 * 1024;
// What may be saved: the file extension and its type.
var SAVED_FILE_KINDS = {
  '.pdf': 'application/pdf',
  '.csv': 'text/csv'
};

function doPost(e) {
  try {
    var request = JSON.parse(e.postData.contents);
    var secret = PropertiesService.getScriptProperties().getProperty('REHAB_SUMMARY_DRIVE_UPLOAD_SECRET');
    if (!secret) {
      return answer_({ ok: false, error: 'the script has no REHAB_SUMMARY_DRIVE_UPLOAD_SECRET' });
    }
    var nowSeconds = Math.floor(Date.now() / 1000);
    if (typeof request.timestamp !== 'number' || Math.abs(nowSeconds - request.timestamp) > LARGEST_TIMESTAMP_AGE_SECONDS) {
      return answer_({ ok: false, error: 'the request is too old' });
    }
    var subject = request.folder_name + '/' + request.file_name;
    var signedMessage = request.timestamp + '\n' + subject + '\n' + request.file_sha256;
    var expectedSignature = toHex_(Utilities.computeHmacSha256Signature(signedMessage, secret, Utilities.Charset.UTF_8));
    if (!equalInConstantTime_(expectedSignature, String(request.signature || ''))) {
      return answer_({ ok: false, error: 'wrong signature' });
    }
    var fileBytes = Utilities.base64Decode(request.file_base64);
    if (fileBytes.length > LARGEST_FILE_BYTES) {
      return answer_({ ok: false, error: 'the file is too large' });
    }
    if (toHex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, fileBytes)) !== request.file_sha256) {
      return answer_({ ok: false, error: 'the file does not match its SHA-256' });
    }
    var folderName = safeName_(request.folder_name);
    var fileName = safeName_(request.file_name);
    var extension = fileName.slice(-4).toLowerCase();
    if (!folderName || !SAVED_FILE_KINDS.hasOwnProperty(extension)) {
      return answer_({ ok: false, error: 'only .pdf and .csv files are saved' });
    }
    var dealFolder = childFolder_(childFolder_(DriveApp.getRootFolder(), REHAB_SUMMARIES_FOLDER_NAME), folderName);
    var file = dealFolder.createFile(Utilities.newBlob(fileBytes, SAVED_FILE_KINDS[extension], fileName));
    return answer_({ ok: true, file_id: file.getId(), folder_url: dealFolder.getUrl() });
  } catch (error) {
    return answer_({ ok: false, error: String(error).slice(0, 200) });
  }
}

// No path separators or special characters: a name is one folder or one file, never a way out of "rehab summaries".
function safeName_(name) {
  return String(name || '').replace(/[\\\/:*?"<>|]/g, '-').replace(/^\.+/, '').slice(0, 200);
}

function childFolder_(parent, folderName) {
  var folders = parent.getFoldersByName(folderName);
  return folders.hasNext() ? folders.next() : parent.createFolder(folderName);
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
