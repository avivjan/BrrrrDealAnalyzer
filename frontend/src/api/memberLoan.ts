import { apiClient } from "./index";
import type {
  MemberLoanAccess,
  MemberLoanAuditEntry,
  MemberLoanIntegrity,
  MemberLoanLedgerRow,
  MemberLoanPreview,
  MemberLoanProposal,
  MemberLoanProposalCreate,
  MemberLoanProposalState,
  MemberLoanStatement,
  MemberLoanSummary,
} from "../types/memberLoan";

/**
 * /member-loan/* — only the two members, on a passkey (the API gates itself).
 * Writes go through the shared client, so a `reauth_required` answer triggers
 * one passkey prompt and a retry (api/index.ts).
 */
export const memberLoanApi = {
  access: () => apiClient.get<MemberLoanAccess>("/member-loan/access").then((r) => r.data),
  summary: (asOfDate: string) =>
    apiClient.get<MemberLoanSummary>("/member-loan/summary", { params: { as_of_date: asOfDate } }).then((r) => r.data),
  ledger: (throughDate: string) =>
    apiClient
      .get<{ through_date: string; rows: MemberLoanLedgerRow[] }>("/member-loan/ledger", { params: { through_date: throughDate } })
      .then((r) => r.data.rows),
  proposals: (state?: MemberLoanProposalState) =>
    apiClient.get<MemberLoanProposal[]>("/member-loan/events", { params: state ? { state } : {} }).then((r) => r.data),
  proposal: (eventId: string) => apiClient.get<MemberLoanProposal>(`/member-loan/events/${encodeURIComponent(eventId)}`).then((r) => r.data),
  preview: (body: MemberLoanProposalCreate) => apiClient.post<MemberLoanPreview>("/member-loan/event-previews", body).then((r) => r.data),
  propose: (body: MemberLoanProposalCreate) => apiClient.post<MemberLoanProposal>("/member-loan/events", body).then((r) => r.data),
  proposeReversal: (eventId: string, reason: string) =>
    apiClient.post<MemberLoanProposal>(`/member-loan/events/${encodeURIComponent(eventId)}/reversal`, { reason }).then((r) => r.data),
  approve: (eventId: string, previewFingerprint: string) =>
    apiClient
      .post<MemberLoanProposal>(`/member-loan/events/${encodeURIComponent(eventId)}/approval`, { preview_fingerprint: previewFingerprint })
      .then((r) => r.data),
  reject: (eventId: string, reason: string) =>
    apiClient.post<MemberLoanProposal>(`/member-loan/events/${encodeURIComponent(eventId)}/rejection`, { reason }).then((r) => r.data),
  cancel: (eventId: string) =>
    apiClient.post<MemberLoanProposal>(`/member-loan/events/${encodeURIComponent(eventId)}/cancellation`).then((r) => r.data),
  statement: (month: string) => apiClient.get<MemberLoanStatement>(`/member-loan/statements/${encodeURIComponent(month)}`).then((r) => r.data),
  statementPdf: (month: string) =>
    apiClient.get<Blob>(`/member-loan/statements/${encodeURIComponent(month)}/pdf`, { responseType: "blob" }).then((r) => r.data),
  ledgerCsv: (throughDate: string) =>
    apiClient.get<Blob>("/member-loan/ledger.csv", { params: { through_date: throughDate }, responseType: "blob" }).then((r) => r.data),
  audit: () => apiClient.get<MemberLoanAuditEntry[]>("/member-loan/audit").then((r) => r.data),
  integrity: () => apiClient.get<MemberLoanIntegrity>("/member-loan/integrity").then((r) => r.data),
  explanation: () => apiClient.get<{ lines: string[] }>("/member-loan/explanation").then((r) => r.data.lines),
};
