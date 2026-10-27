/**
 * Big Whales Deal Analyzer: save signed Member Loan documents to Google Drive.
 *
 * Runs as a Google Apps Script web app owned by bigwhalesllc@gmail.com. The
 * web service POSTs each fully signed PDF here (BL/memberLoan/common/member_loan_google_drive.py);
 * this script saves it in the Drive folder "loan agreements", creating the
 * folder the first time.
 *
 * Every request must carry an HMAC-SHA256 signature made with the shared
 * secret, over "<timestamp>\n<file name>\n<SHA-256 of the PDF>", and a
 * timestamp less than 5 minutes old. Anything else is refused, so the web app
 * URL alone lets nobody write to the Drive.
 *
 * Set up (once):
 *   1. Signed in as bigwhalesllc@gmail.com, open https://script.google.com and
 *      create a new project. Paste this whole file over the default code.
 *   2. Project Settings (gear) > Script Properties > Add property:
 *        MEMBER_LOAN_DRIVE_UPLOAD_SECRET = the same secret as on Render.
 *   3. Deploy > New deployment > type "Web app":
 *        Execute as: Me (bigwhalesllc@gmail.com)
 *        Who has access: Anyone
 *      Authorize when asked (Advanced > Go to project). Copy the web app URL
 *      (it ends in /exec): it becomes MEMBER_LOAN_DRIVE_UPLOAD_URL on Render.
 */

var LARGEST_TIMESTAMP_AGE_SECONDS = 300;
var LOAN_AGREEMENTS_FOLDER_NAME = 'loan agreements';

function doPost(e) {
  try {
    var request = JSON.parse(e.postData.contents);
    var secret = PropertiesService.getScriptProperties().getProperty('MEMBER_LOAN_DRIVE_UPLOAD_SECRET');
    if (!secret) {
      return answer_({ ok: false, error: 'the script has no MEMBER_LOAN_DRIVE_UPLOAD_SECRET' });
    }
    var nowSeconds = Math.floor(Date.now() / 1000);
    if (typeof request.timestamp !== 'number' || Math.abs(nowSeconds - request.timestamp) > LARGEST_TIMESTAMP_AGE_SECONDS) {
      return answer_({ ok: false, error: 'the request is too old' });
    }
    var signedMessage = request.timestamp + '\n' + request.file_name + '\n' + request.pdf_sha256;
    var expectedSignature = toHex_(Utilities.computeHmacSha256Signature(signedMessage, secret, Utilities.Charset.UTF_8));
    if (!equalInConstantTime_(expectedSignature, String(request.signature || ''))) {
      return answer_({ ok: false, error: 'wrong signature' });
    }
    var pdfBytes = Utilities.base64Decode(request.pdf_base64);
    if (toHex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, pdfBytes)) !== request.pdf_sha256) {
      return answer_({ ok: false, error: 'the PDF does not match its SHA-256' });
    }
    var fileName = String(request.file_name).replace(/[\\\/:*?"<>|]/g, '-');
    if (fileName.slice(-4).toLowerCase() !== '.pdf') {
      return answer_({ ok: false, error: 'only PDF files are saved' });
    }
    var folder = loanAgreementsFolder_(LOAN_AGREEMENTS_FOLDER_NAME); // never a name from the request
    var file = folder.createFile(Utilities.newBlob(pdfBytes, 'application/pdf', fileName));
    return answer_({ ok: true, file_id: file.getId() });
  } catch (error) {
    return answer_({ ok: false, error: String(error).slice(0, 200) });
  }
}

function loanAgreementsFolder_(folderName) {
  var folders = DriveApp.getRootFolder().getFoldersByName(folderName);
  return folders.hasNext() ? folders.next() : DriveApp.getRootFolder().createFolder(folderName);
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
