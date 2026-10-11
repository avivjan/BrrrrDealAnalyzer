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
  caller_may_approve_or_reject: boolean;
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
}

/** A refusal from the API: `detail.message` is plain language for the member. */
export interface MemberLoanRefusal {
  message: string;
  code: string | null;
  live_preview?: MemberLoanPreview;
}
