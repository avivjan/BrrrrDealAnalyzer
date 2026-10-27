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
  MemberLoanSignatureMeaning,
  MemberLoanSignatureSubmit,
  MemberLoanSigningCompletion,
  MemberLoanSigningDocument,
  MemberLoanSigningRequest,
  MemberLoanStatement,
  MemberLoanSummary,
  MemberLoanPasskeySigningOptions,
} from "../types/memberLoan";

/**
 * /member-loan/* — only the two members, on a passkey (the API gates itself).
 * Writes go through the shared client, so a `reauth_required` answer triggers
 * one passkey prompt and a retry (api/index.ts). Signing needs no such prompt:
 * it carries its own passkey assertion over the document (signingPasskeyOptions,
 * then submitSignature).
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
  startChangeSigning: (body: MemberLoanProposalCreate) =>
    apiClient.post<MemberLoanSigningRequest>("/member-loan/change-documents", body).then((r) => r.data),
  startReversalSigning: (eventId: string, reason: string) =>
    apiClient
      .post<MemberLoanSigningRequest>(`/member-loan/events/${encodeURIComponent(eventId)}/reversal-documents`, { reason })
      .then((r) => r.data),
  startDocumentSigning: (documentId: string, signatureMeaning: MemberLoanSignatureMeaning, objectionReason?: string) =>
    apiClient
      .post<MemberLoanSigningRequest>(`/member-loan/documents/${encodeURIComponent(documentId)}/signing-requests`, {
        signature_meaning: signatureMeaning,
        objection_reason: objectionReason ?? null,
      })
      .then((r) => r.data),
  signingPasskeyOptions: (signingRequestId: string) =>
    apiClient
      .post<MemberLoanPasskeySigningOptions>(`/member-loan/signing-requests/${encodeURIComponent(signingRequestId)}/passkey-options`)
      .then((r) => r.data),
  submitSignature: (signingRequestId: string, body: MemberLoanSignatureSubmit) =>
    apiClient
      .post<MemberLoanSigningCompletion>(`/member-loan/signing-requests/${encodeURIComponent(signingRequestId)}/signature`, body)
      .then((r) => r.data),
  signingRequestPdf: (signingRequestId: string) =>
    apiClient
      .get<Blob>(`/member-loan/signing-requests/${encodeURIComponent(signingRequestId)}/pdf`, { responseType: "blob" })
      .then((r) => r.data),
  documents: (waitingForMe = false) =>
    apiClient.get<MemberLoanSigningDocument[]>("/member-loan/documents", { params: waitingForMe ? { waiting_for_me: true } : {} }).then((r) => r.data),
  document: (documentId: string) =>
    apiClient.get<MemberLoanSigningDocument>(`/member-loan/documents/${encodeURIComponent(documentId)}`).then((r) => r.data),
  documentPdf: (documentId: string) =>
    apiClient.get<Blob>(`/member-loan/documents/${encodeURIComponent(documentId)}/pdf`, { responseType: "blob" }).then((r) => r.data),
  signedCopyPdf: (documentId: string) =>
    apiClient.get<Blob>(`/member-loan/documents/${encodeURIComponent(documentId)}/signed-pdf`, { responseType: "blob" }).then((r) => r.data),
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
