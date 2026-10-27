/**
 * The Member Loan API's shapes (BackEnd/ReqRes/common/member_loan_schemas.py).
 *
 * Every amount is a string with two decimals ("1000.00"). The frontend never
 * does loan arithmetic: it shows what the server computed and sends what the
 * member typed.
 */

export type MemberLoanEventType =
  | "lender_withdrawal"
  | "lender_additional_advance"
  | "yarden_capital_contribution_reduction"
  | "yarden_additional_withdrawal_increase"
  | "interest_payment_election";

export type MemberLoanProposalState = "pending" | "approved" | "rejected" | "cancelled" | "expired";

export interface MemberLoanBuckets {
  original_principal: string;
  capitalized_interest: string;
  total_balance: string;
  accrued_interest: string;
  interest_payable: string;
  amount_owed: string;
  lender_capital_credited: string;
}

export interface MemberLoanAllocation {
  from_interest_payable: string;
  from_accrued_interest: string;
  from_capitalized_interest: string;
  from_original_principal: string;
}

export interface MemberLoanPreview {
  effective_date: string;
  buckets_before: MemberLoanBuckets;
  buckets_after: MemberLoanBuckets;
  allocation: MemberLoanAllocation | null;
  preview_fingerprint: string;
}

export interface MemberLoanAccess {
  allowed: boolean;
  username: string;
  display_name: string;
  role: "lender" | "yarden";
  other_member_display_name: string;
  proposals_waiting_for_you: number;
  documents_waiting_for_your_signature: number;
}

export interface MemberLoanSummary {
  as_of_date: string;
  buckets: MemberLoanBuckets;
  loan_effective_date: string;
  maturity_date: string;
  original_principal_at_start: string;
  proposals_waiting_for_you: number;
  proposals_waiting_for_other_member: number;
}

export interface MemberLoanProposal {
  id: string;
  proposal_sequence: number;
  event_type: MemberLoanEventType | "reversal";
  plain_event_name: string;
  effective_date: string;
  amount: string | null;
  interest_election_choice: "reinvest" | "cash" | null;
  written_agreement_date: string | null;
  written_agreement_description: string | null;
  payment_reference: string | null;
  note: string | null;
  reverses_event_id: string | null;
  reversed_event_summary: string | null;
  reversal_reason: string | null;
  state: MemberLoanProposalState;
  proposed_by_display_name: string;
  proposed_at: string;
  decided_by_display_name: string | null;
  decided_at: string | null;
  decision_reason: string | null;
  preview_at_proposal: MemberLoanPreview;
  live_preview: MemberLoanPreview | null;
  live_preview_problem: string | null;
  figures_changed_since_proposal: boolean;
  signing_document_id: string | null;
  caller_may_sign_or_reject: boolean;
  caller_may_cancel: boolean;
  caller_may_propose_reversal: boolean;
  includes_yarden_increase_warning: boolean;
}

export interface MemberLoanProposalCreate {
  event_type: MemberLoanEventType;
  effective_date: string;
  amount?: string | null;
  interest_election_choice?: "reinvest" | "cash" | null;
  written_agreement_date?: string | null;
  written_agreement_description?: string | null;
  payment_reference?: string | null;
  note?: string | null;
}

export interface MemberLoanLedgerRow {
  row_date: string;
  row_kind: string;
  plain_description: string;
  event_id: string | null;
  amount: string | null;
  allocation: MemberLoanAllocation | null;
  interest_added_to_debt: string | null;
  interest_moved_to_interest_payable: string | null;
  buckets_after: MemberLoanBuckets;
  proposed_by_display_name: string | null;
  approved_by_display_name: string | null;
}

export interface MemberLoanStatementDocument {
  title: string;
  statement_month: string;
  statement_date: string;
  summary_rows: [string, string][];
  what_happened_sentences: string[];
  interest_period_lines: string[];
  interest_total_lines: string[];
  debt_equation_lines: string[];
  amount_owed_lines: string[];
  how_it_works_lines: string[];
  warnings: string[];
  binding_sentence: string;
  engine_version: string;
  ledger_fingerprint: string;
}

export interface MemberLoanStatement {
  statement_month: string;
  document: MemberLoanStatementDocument;
  is_final: boolean;
  sent_at: string | null;
  objection_deadline: string | null;
  sent_to: string[];
  signing_document_id: string | null;
}

export interface MemberLoanAuditEntry {
  audit_sequence: number;
  recorded_at: string;
  actor_display_name: string;
  action: string;
  event_id: string | null;
  state_before: Partial<MemberLoanBuckets> | null;
  state_after: Partial<MemberLoanBuckets> | null;
  detail: Record<string, unknown> | null;
}

export interface MemberLoanIntegrity {
  intact: boolean;
  problems: string[];
  proposals_checked: number;
  decisions_checked: number;
  audit_entries_checked: number;
  signing_documents_checked: number;
  signatures_checked: number;
  signed_copies_checked: number;
}

/** A refusal from the API: `detail.message` is plain language for the member. */
export interface MemberLoanRefusal {
  message: string;
  code: string | null;
}

// -- signing (tasks/todo/MemberLoanSigning.md) ------------------------------------

export type MemberLoanSignatureMeaning = "signed" | "objected";
export type MemberLoanSigningPurpose = "propose_change" | "propose_reversal" | "sign_document";

/** A signer as the document lists them; `statement_text` is what their signature says. */
export interface MemberLoanDocumentSignerEntry {
  username: string;
  legal_name: string;
  role: string;
  role_label: string;
  statement_text: string;
  signs_as?: "proposer" | "counterparty";
}

/** The structured content a document's PDF is drawn from (BL/memberLoan/common/member_loan_signing_documents.py). */
export interface MemberLoanDocumentContent {
  document_kind: "loan_change" | "monthly_statement";
  title: string;
  signers: MemberLoanDocumentSignerEntry[];
  // a Loan Change Record
  record_number?: number;
  prepared_on?: string;
  agreement_reference?: string;
  parties_lines?: string[];
  change_rows?: [string, string][];
  contract_basis_lines?: string[];
  figures_effective_date?: string;
  figures_rows?: [string, string, string][];
  allocation_lines?: string[];
  effect_lines?: string[];
  warnings?: string[];
  // a monthly statement
  statement_month?: string;
  month_label?: string;
  statement_date?: string;
  amount_owed?: string;
  acknowledgment_intro_lines?: string[];
  statement_document?: MemberLoanStatementDocument;
}

export interface MemberLoanSigningRequest {
  signing_request_id: string;
  signing_purpose: MemberLoanSigningPurpose;
  document_id: string | null;
  document_sha256: string;
  document_content: MemberLoanDocumentContent;
  signature_meaning: MemberLoanSignatureMeaning;
  objection_reason: string | null;
  signature_statement_text: string;
  full_legal_name_to_type: string;
  electronic_signature_consent_text: string;
  expires_at: string;
}

export interface MemberLoanPasskeySigningOptions {
  passkey_challenge_id: string;
  options: string;
}

export interface MemberLoanDocumentSigner {
  username: string;
  display_name: string;
  legal_name: string;
  role_label: string;
  status: "waiting" | "signed" | "objected";
  signed_at: string | null;
  objection_reason: string | null;
}

export interface MemberLoanSignedCopyDelivery {
  delivery_channel: "email" | "google_drive";
  delivery_status: "sent" | "failed";
  attempted_at: string;
}

export interface MemberLoanSigningDocument {
  id: string;
  document_kind: "loan_change" | "monthly_statement";
  title: string;
  event_id: string | null;
  statement_month: string | null;
  record_number: number | null;
  created_at: string;
  document_sha256: string;
  content: MemberLoanDocumentContent;
  signers: MemberLoanDocumentSigner[];
  caller_must_act: boolean;
  caller_may_object: boolean;
  proposal_state: MemberLoanProposalState | null;
  response_deadline: string | null;
  is_complete: boolean;
  completed_at: string | null;
  signed_copy_sha256: string | null;
  deliveries: MemberLoanSignedCopyDelivery[];
}

export interface MemberLoanSignatureSubmit {
  typed_full_legal_name: string;
  electronic_signature_consent_confirmed: boolean;
  drawn_signature_png_base64: string;
  passkey_challenge_id: string;
  passkey_credential: unknown;
}

export interface MemberLoanSigningCompletion {
  document: MemberLoanSigningDocument;
  proposal: MemberLoanProposal | null;
}
