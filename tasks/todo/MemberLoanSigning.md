# Member Loan e-signing (plan)

Branch `MemberLoanSigning`, cut from `main`. Approved by the owner on 2026-10-27.

## בקצרה (עברית)

- **כפתור האישור מוסר.** כל שינוי בהלוואה יוצר מסמך משפטי ("Loan Change Record"). המסמך מסביר מה משתנה, לפי איזה סעיף בהסכם, ואת המספרים לפני ואחרי.
  - מי שמציע את השינוי חותם ראשון. הצד השני חותם כדי לאשר.
  - ההלוואה באתר מתעדכנת רק אחרי ששניכם חתמתם.
- **הדוח החודשי** כולל דף הצהרה וחתימות לפי תפקיד:
  - אתה מאשר שהמספרים נכונים.
  - ירדן חותמ/ת בשם החברה וכערב/ה: החוב נכון, אין טענות, החברה מתחייבת לשלם, והערבות בתוקף.
  - מה-1 בחודש נשלחת תזכורת כל יום עד שחותמים, ולכל היותר 30 יום.
- **החתימה**, בדומה ל-DocuSign: קוראים את המסמך, מקלידים שם מלא, מציירים חתימה, מסמנים הסכמה ומאשרים ב-passkey. ה-passkey חותם קריפטוגרפית על טביעת האצבע של המסמך עצמו.
- **כל מסמך חתום** נשלח לשלוש הכתובות.
  - הכותרת היא `whales loan update` לשינוי, או `whales loan statement` לדוח החודשי.
  - המסמך נשמר גם בגוגל דרייב של החברה, בתיקייה `loan agreements`.

## Context

The owner and Yarden signed **Amendment No. 1** (doc: https://claude.ai/artifact/39UXoC9JEiZ42FNXmYQUfB). The amendment defines how a Member signs in the Software:
- **§1.2:** view the record, type the full legal name, tick "I agree this is my electronic signature", and complete the passkey confirmation.
- **§1.4:** e-mail a signed PDF to the three notice addresses.
- **§1.5 and §1.6:** keep a tamper-evident record.
- **§1.8:** the steps may be added later, and earlier approvals stay valid.
- **§2.3:** Yarden's signature on a withdrawal or interest election confirms facts only.
- **§6.2 and §6.3:** a statement can be signed or objected to, with daily reminders up to 30 days. Signing is not required for a statement to become binding.

Today a counterparty approves a proposal with a button: `decide_member_loan_event` in `BackEnd/BL/memberLoan/common/member_loan_ledger_service.py`, with passkey step-up and the preview fingerprint (R7). The owner wants that replaced by a legally stronger signing flow, for every change and every monthly statement. Signed copies go to the three e-mail addresses and to the company's Google Drive.

## Decisions

| # | Decision |
|---|---|
| S1 | **Signing replaces the Approve button.** Every proposal of the 5 event types, plus reversals, creates a *Loan Change Record* PDF. The proposer signs it when proposing, and nothing is stored until they do. The counterparty signs it to approve. The existing `approved` decision row is written **in the same transaction as the second signature**, so the engine (R5) stays unchanged. `POST /member-loan/events/{id}/approval` is removed and returns 410 "approval now requires signing". |
| S2 | **The signing ceremony** follows Amendment §1.2 and §1.8. See "Signing ceremony" below for the full steps. |
| S3 | **Wording depends on the role and event type.** For a withdrawal or interest election, the counterparty's signature *confirms the facts* (Amendment §2.3). For an advance, a Yarden contribution, a Yarden withdrawal (§7A) or a reversal, it *agrees to the change* (§1.3). |
| S4 | **Stale figures.** The document prints the before and after figures. If another approval changed them, the document can no longer be signed. The proposal becomes `expired` with reason "figures changed". It can be re-proposed in one click, prefilled, and both members sign the new record. This replaces the R7 "review the new preview" path. |
| S5 | **Reject and cancel stay as they are:** passkey step-up, a required reason for rejection, and an e-mail to both members. They create no signed document. |
| S6 | **The monthly statement document** is the existing six-section statement PDF plus an *Acknowledgment and signatures* page. The wording depends on the role: the owner chose it. Each member may **Sign** or **Object**. An objection takes a reason and is passkey-signed the same way. Not signing never blocks the statement from becoming binding (§6.3). |
| S7 | **E-mail.** Each signed copy goes to the lender, Yarden and the company address, all read from env, with the PDF attached. The subject is exactly `whales loan update` for a change and `whales loan statement` for a statement. Requests and reminders go only to the member who still has to sign. Their subjects are `whales loan update – please sign` and `whales loan statement – please sign`. Links never carry a token and never act on their own. |
| S8 | **Statement reminders:** one e-mail a day, from 09:00 New York time, to each member who has not signed or objected. The first request goes out with the statement on the 1st. Reminders stop when both have acted, or after the 30th day after sending (§6.2, the owner chose this). |
| S9 | **Google Drive.** A Google Apps Script web app, owned by bigwhalesllc@gmail.com, saves each signed PDF into the folder `loan agreements`, creating it if needed. The backend POSTs the PDF with an HMAC-SHA256 signature. See "Google Drive delivery" below. |
| S10 | **Delivery state is append-only.** Each e-mail or Drive attempt is a delivery row. Failures are retried by the scheduler thread up to 3 times. A failure never rolls back a signature. |
| S11 | **Changeover.** Events approved before this release stay valid without a signature (Amendment §1.8). Proposals still pending at deploy are expired with reason "signing replaced approval", and both members are told how to re-propose. A statement month already sent without a signing document gets one created by the scheduler's next check. |
| S12 | **MCP** keeps excluding `/member-loan` entirely (D12). No new MCP tools. |

### Signing ceremony (S2)

1. Show the document: an HTML rendition of the same structured content, plus "Open the PDF".
2. Type your full legal name. It must match `MEMBER_LOAN_LENDER_LEGAL_NAME` or `MEMBER_LOAN_YARDEN_LEGAL_NAME`, which default to "Aviv Jan" and "Yarden Kelly". Case and spacing are ignored.
3. Draw a signature on a pad. It works with touch and mouse, produces a PNG of at most 60 KB, and offers clear and redo.
4. Tick: "I agree this is my electronic signature and that it has the same effect as my handwritten signature (Amendment No. 1, Section 1)."
5. Sign with your passkey. The WebAuthn challenge is `SHA-256(document_pdf_sha256 ‖ 32 random bytes)`, so the passkey's cryptographic signature covers this exact document.
6. The raw assertion is stored as evidence: authenticatorData, clientDataJSON, the signature and the credential id.

### Google Drive delivery (S9)

**Why Apps Script:** a service account cannot store files in a personal Gmail account's Drive, because it has no storage quota. Setting up OAuth for bigwhalesllc@gmail.com needs a Cloud console project, a consent screen and a refresh token. Apps Script takes about 5 minutes of copy and paste.

**How the request is checked:**
- The script checks the signature with `Utilities.computeHmacSha256Signature`.
- It refuses timestamps older than 5 minutes.
- It returns the Drive file id, which is stored on the delivery row.

**File names:**
- A change: `2026-10-15 whales loan update #7 – Lender withdrawal $1,000.00 – signed.pdf`
- A statement: `2026-11-01 whales loan statement – October 2026 – signed.pdf`

### Legal wording, draft for the owner to review (and ideally a Florida attorney)

**Loan Change Record, proposer:**
> "I, {legal name}, propose this change to the Loan Agreement dated October 6, 2026, as amended by Amendment No. 1. I sign this Change Record. I confirm the facts stated in it are true."

**Loan Change Record, counterparty agreeing** (advance, Yarden contribution, §7A withdrawal, reversal):
> "I, {legal name}, agree to this change. I sign as {Lender and Member | Member and on behalf of Big Whales AY LLC}. This Change Record is a written agreement signed by both Members under Section 1.3 of Amendment No. 1. Every other term of the Agreement stays unchanged."

**Loan Change Record, counterparty confirming** (withdrawal, interest election):
> "I, {legal name}, confirm that the notice was given{ and that $X was paid on DATE}. Under Section 2.3 of Amendment No. 1, this is a confirmation of fact, not consent."

**Statement, Lender:**
> "I, Aviv Jan, Lender, have reviewed this statement for {Month YYYY}. I confirm that its figures are correct and I have no objection to it."

**Statement, Yarden** (for Big Whales AY LLC, as its Member, and personally as Guarantor):
> 1. The figures in this statement are correct and I have no objection to it.
> 2. Borrower owes Lender the Amount Owed of ${X} as of {date}, plus interest from that date under the Agreement.
> 3. This amount is owed without any defense, offset or counterclaim. Any that existed on this date are waived.
> 4. Borrower promises to pay it as the Agreement requires, including on demand under Section 6.1 and on the Maturity Date.
> 5. The personal guarantee in Section 10, and the security in Section 8 of Amendment No. 1, remain in full force for this amount.
> 6. This is a written acknowledgment of the debt.

**Objection:**
> "I, {legal name}, object to this statement in writing under Section 8.3 of the Agreement for this reason: {reason}."

### The Loan Change Record PDF

It is built in ReportLab, reusing the statement PDF's styles. It has these sections:
1. Parties.
2. What changes: type, amount, effective date, written-agreement and payment references, note.
3. Contract basis: the section it relies on.
   - Withdrawal: §6.1, §6.3 and Amendment §2.
   - Advance: §2.2 as amended.
   - Yarden contribution: §7 as amended.
   - Yarden withdrawal: §7A.
   - Interest election: §4.4 and Amendment §2.4.
   - Reversal: the cancelled record number and the reason.
4. Figures before and after: the buckets table and Amount Owed.
5. "This record updates the existing loan. Every other term stays unchanged."
6. The signature statements.

**The final signed copy** is the unsigned pages plus a **Signature certificate** page. For each signer it shows:
- name, role, and whether they signed or objected;
- the drawn signature and the typed name;
- the time in New York and in UTC;
- IP, device and the short passkey credential id;
- the document's SHA-256.

## Data model

New tables, each append-only with a trigger and a hash chain, unless marked mutable:

| Table | Key columns |
|---|---|
| `member_loan_signing_documents` | **Identity:** `id`, `document_sequence`, `document_kind` (`loan_change` \| `monthly_statement`), `event_id` (unique, nullable), `statement_month` (unique, nullable). **Content:** `title`, `document_content` (JSON), `unsigned_pdf` (bytes), `unsigned_pdf_sha256`. **Signing:** `required_signer_usernames`. **Chain:** `created_at`, `previous_document_hash`, `document_hash`. |
| `member_loan_signatures` | **Who and what:** `id`, `signature_sequence`, `document_id`, `signer_user_id`, `signer_username`, `signer_role`, `signature_meaning` (`signed` \| `objected`), `objection_reason`. **Ceremony:** `typed_full_legal_name`, `signature_statement_text`, `drawn_signature_png`, `signed_document_sha256`. **Passkey evidence:** `webauthn_credential_id`, `webauthn_authenticator_data`, `webauthn_client_data_json`, `webauthn_signature`. **Context:** `request_ip`, `user_agent`, `device_id`, `signed_at`. **Chain:** `previous_signature_hash`, `signature_hash`. **Rule:** unique (`document_id`, `signer_username`). |
| `member_loan_signed_copies` | `id`, `document_id` (unique), `signed_pdf`, `signed_pdf_sha256`, `completed_at`, plus the hash chain. |
| `member_loan_signed_copy_deliveries` | `id`, `signed_copy_id`, `delivery_channel` (`email` \| `google_drive`), `delivery_status` (`sent` \| `failed`), `external_file_id`, `error_text`, `attempted_at`. |
| `member_loan_statement_signature_reminders` | `statement_month`, `recipient_username`, `reminder_date`. **Rule:** unique on all three, so there is at most one a day. |
| `member_loan_signing_requests` | **Mutable**, the same pattern as auth challenges. `id`, `user_id`, `document_id` or a `proposal_draft` (JSON, plus the draft PDF), `document_sha256`, `webauthn_challenge`, `expires_at` (10 min), `consumed_at`. |

## API (all under `/member-loan`, all self-gated; POSTs take CSRF and the rate limit)

| Endpoint | Purpose |
|---|---|
| `POST /member-loan/change-documents` | Body: the proposal fields. Validates as `propose_member_loan_event` does, renders the draft record, and stores a signing request. Returns the document content, the PDF link and the passkey options. |
| `POST /member-loan/events/{id}/reversal-documents` | The same, for a reversal. |
| `GET /member-loan/signing-requests/{id}/pdf` | The draft PDF. The requester only. |
| `POST /member-loan/events` | **Changed.** Body: `signing_request_id`, `typed_full_legal_name`, `consent_confirmed`, `drawn_signature_png_base64` and the passkey credential. In one transaction it writes the event, the document, the proposer's signature and the audit row. |
| `POST /member-loan/events/{id}/reversal` | **Changed** the same way. |
| `GET /member-loan/documents?kind=&waiting_for_me=` | Documents and their signature status. |
| `GET /member-loan/documents/{id}` and `…/pdf` and `…/signed-pdf` | One document, its unsigned PDF, its signed copy. |
| `POST /member-loan/documents/{id}/signing-requests` | Passkey options bound to that document. Refused if it is stale (S4), already signed by the caller, or the caller is not a required signer. |
| `POST /member-loan/documents/{id}/signatures` | Body: as for proposing, plus `signature_meaning` and `objection_reason`. A counterparty's signature on a change also approves it (S1). |
| `POST /member-loan/events/{id}/approval` | **Removed:** returns 410. |

The signing endpoints do not need a recent step-up, because each one carries its own fresh passkey assertion. They keep the reader gate, CSRF and the rate limit. The assertion is checked with `_verify_assertion` (`BackEnd/BL/auth/login.py`) under a new challenge kind `member_loan_signature`, with `expected_user_id` set to the signer. `begin_login` gets an optional `challenge` argument.

## Reused code

- **Ledger:** `member_loan_ledger_service.py`. Reuse `propose_member_loan_event` and `propose_member_loan_reversal` validation (split out to return a validated candidate), `_append_decision`, `append_member_loan_audit_entry`, `live_preview_for`, `_refuse_if_month_locked` and `acquire_member_loan_write_lock`.
- **Hash chains:** `member_loan_hash_chain.py`.
- **Append-only triggers:** `migrations/steps/member_loan_append_only_triggers.py`. Add the new tables to `MEMBER_LOAN_APPEND_ONLY_TABLE_NAMES`.
- **E-mail:** `member_loan_mail_transport.deliver_member_loan_email`.
- **Notifications:** `member_loan_notifications.send_member_loan_notification_after_commit`. "Proposed" becomes the please-sign request, and "approved" is replaced by the signed-copy e-mail.
- **Statements:** `member_loan_statement_pdf.render_member_loan_statement_pdf`, its styles, `build_member_loan_statement_for_month` and `member_loan_statement_sender.send_member_loan_statement`. A successful send also creates the statement's signing document.
- **Scheduler:** `member_loan_statement_schedule.py`. It gains reminders, statement-document creation for months sent without one, and delivery retries.
- **Frontend passkeys:** `@simplewebauthn/browser` `startAuthentication`, the same way as `authStore.reauth()`.
- **Frontend building blocks:** `Ui*` primitives, `MemberLoanBucketsTable.vue` and `LoanAmountInput.vue`.

## Frontend

- **`MemberLoanSigningDialog.vue`:** a DocuSign-like stepper with four steps:
  1. Review: the HTML rendition and "Open PDF".
  2. Name.
  3. Draw.
  4. Consent and "Sign with passkey".
- **`MemberLoanSignaturePad.vue`:** a canvas with pointer events, `touch-action: none`, clear, and PNG export. No new dependency.
- **`MemberLoanProposeForm.vue`:** "Preview" becomes "Review and sign", which opens the dialog.
- **`MemberLoanProposalCard.vue`:** Approve becomes "Review and sign". It shows signature chips ("Signed by Aviv ✓ · Waiting for Yarden") and download links for the record and the signed copy.
- **`MemberLoanStatementPanel.vue`:** each month shows its signature status, Sign and Object (with reason) buttons, and the statement and signed-copy downloads.
- **`views/MemberLoan.vue`:** the "Waiting for approval" tab becomes "Waiting for your signature". The nav badge counts documents waiting for the caller.
- **Routes:** a new `/member-loan/sign/:documentId` for the e-mail deep link. `/member-loan/approvals/:eventId` redirects to it.
- **Plumbing:** `api/memberLoan.ts`, `types/memberLoan.ts`, `stores/memberLoanStore.ts` and `utils/memberLoanText.ts`.

## Security task (contents of `.claude/security.md`)

> "Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo"

On top of that:
- **Signing requests:** single-use, expire after 10 minutes, bound to the user and to the document SHA.
- **Passkey assertions:** the challenge is bound to the document, `expected_user_id` is the signer, and user verification is required.
- **Who may sign:** only a required signer, once.
- **E-mail links:** token-free.
- **Drawn signature:** size-limited and PNG magic-checked.
- **Name in the PDF:** the typed name is escaped in ReportLab paragraphs.
- **Drive upload:** HMAC with a timestamp; the secret and URL come from env only, and the script refuses unsigned requests.
- **Stored PDFs:** served only through the gated routes, with `Content-Disposition` and `X-Content-Type-Options`.
- **Then the repo-wide pass,** with findings in Review.

## Todo (agent wall-clock)

- [x] **0** (10 min): Branch `MemberLoanSigning` from the latest `main`. Copy this plan to `tasks/todo/MemberLoanSigning.md`.
- [x] **1** (60 min): Models for the six tables, append-only triggers, hash chains, crud, test TRUNCATE.
- [x] **2** (45 min): The passkey signing ceremony: document-bound challenge, `member_loan_signature` kind, signing requests, assertion evidence stored.
- [x] **3** (90 min): Change Record content builder, its PDF, and the Signature certificate page builder. The final signed-copy renderer.
- [x] **4** (90 min):
  - Propose by signing: drafts, `POST /events` and reversal.
  - Countersign approves in the same transaction.
  - Stale documents expire (S4).
  - The approval route returns 410.
  - The changeover expiry (S11).
- [x] **5** (60 min): The statement acknowledgment page, the statement signing document created on send, Sign and Object.
- [x] **6** (60 min): Delivery:
  - signed-copy e-mail to the three env addresses, with the exact subjects;
  - please-sign requests;
  - the Drive uploader with HMAC;
  - delivery rows and the audit.
- [x] **7** (40 min): Scheduler: daily reminders up to 30 days, documents for months sent without one, delivery retries (3).
- [x] **8** (20 min): `BackEnd/integrations/google_drive_loan_agreements.gs`, the Apps Script, plus step-by-step setup notes.
- [x] **9** (10 min): MCP: assert that the new routes are excluded with `/member-loan`, and that the OpenAPI golden is updated.
- [ ] **10** (180 min): Frontend:
  - signing dialog and signature pad;
  - propose form, proposal card and statement panel;
  - the sign route and redirect;
  - store, API and types; the badge.
- [ ] **11** (60 min): E2E with two browser contexts and virtual authenticators.
- [x] **12** (15 min): `verify_regression.py snapshot`. Review the diff, and make a `Golden update:` commit if needed.
- [ ] **13** (40 min): The security task, then the repo-wide pass.
- [ ] **14** (25 min): README: the signing flow, the new env variables, Apps Script setup. The Review section.
- [ ] **15** (15 min): Push `MemberLoanSigning` and open the PR.
- [ ] **16** (owner, about 10 min, guided): Paste the Apps Script into bigwhalesllc's Google account and deploy it. I set these Render env vars:
  - `MEMBER_LOAN_COMPANY_EMAIL`
  - `MEMBER_LOAN_LENDER_LEGAL_NAME`
  - `MEMBER_LOAN_YARDEN_LEGAL_NAME`
  - `MEMBER_LOAN_DRIVE_UPLOAD_URL`
  - `MEMBER_LOAN_DRIVE_UPLOAD_SECRET`

Total is about 12.5 hours of agent time.

## Tests

### Unit (pytest, no DB)

- **The Change Record for each of the 6 types:**
  - the right contract section;
  - the right counterparty wording (agree, or confirm under §2.3);
  - the before and after figures equal the engine preview;
  - the PDF text re-parses to the same figures.
- **Statement acknowledgment wording by role:** the Lender's text has no promise to pay. Yarden's text has items 1–6 with the right Amount Owed and date.
- **The signature certificate page** lists every signer, the time in NY and UTC, the SHA-256 and the drawn image.
- **The legal-name check:** case and spacing are ignored, a wrong name is refused.
- **Drawn signature validation:** the size limit, and that it really is a PNG.
- **The HMAC request builder** and file names.
- **Reminder schedule:** no reminder before 09:00 NY or after day 30, one a day, none once the member has signed or objected.

### Integration (pytest, test Postgres)

**Proposing:**
- A proposal without a signature changes nothing and stores nothing.
- Signing a draft creates the event, the document and the proposer signature, and e-mails a please-sign request to the counterparty only.
- A tampered PDF hash, a replayed or expired signing request, another user's assertion, or a wrong legal name each get refused.

**Approving:**
- The counterparty's signature writes the `approved` decision. The summary updates, and the signed copy is e-mailed to 3 addresses with subject `whales loan update` and uploaded to Drive (faked).
- The proposer cannot countersign: 403.
- A second signature by the same member gets 409.
- A stale document cannot be signed. The proposal expires with "figures changed" and can be re-proposed.
- `/approval` returns 410.
- Reject and cancel are unchanged.

**Statements:**
- A real send creates the signing document, which needs both members.
- Sign, and object with a reason.
- Once both have acted, the signed copy goes out with subject `whales loan statement`.
- Reminders are idempotent per day and stop at 30 days. A dry run creates nothing.

**Delivery:**
- An SMTP or Drive failure keeps the signatures and writes a `failed` delivery row, and the scheduler retries up to 3 times.

**Changeover:**
- Pending proposals expire with "signing replaced approval". Approved events stay in effect.

**Records:**
- Raw UPDATE and DELETE on the new tables raise.
- A tampered signature or document breaks `GET /member-loan/integrity`.

**MCP and regression:**
- The routes are excluded.
- The OpenAPI golden matches.

### E2E (Playwright, two browser contexts, each with its own virtual authenticator)

- Aviv proposes a withdrawal: review, type name, draw, consent, passkey. The figures do not change.
- Yarden opens the e-mail deep link `/member-loan/sign/<id>`, reviews and signs. Amount Owed updates. Both see "Signed by both" and can download the signed copy.
- Yarden proposes an advance and Aviv rejects it with a reason. Nothing changes.
- On the statement for a closed month, Aviv signs and Yarden objects with a reason. Both statuses show.
- The signature pad works on Mobile Chrome, with touch. Axe and CSP pass.

## Verification

1. Backend:
   ```
   cd BackEnd && pytest && python3 verify_regression.py verify
   ```
2. Frontend:
   ```
   cd frontend && npm test && npm run build && npm run verify:ui -- --fast && npm run e2e
   ```
3. Locally, render a sample Change Record, a statement with its acknowledgment page and a signed copy to files, and review them by hand.
4. After deploy: run one real cycle on a $1 withdrawal: both sign, check the e-mail in all 3 inboxes and the file in Drive `loan agreements`. Then reverse it the same way.
