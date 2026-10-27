import { startAuthentication } from "@simplewebauthn/browser";
import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { memberLoanApi } from "../api/memberLoan";
import type {
  MemberLoanAccess,
  MemberLoanAuditEntry,
  MemberLoanIntegrity,
  MemberLoanLedgerRow,
  MemberLoanProposal,
  MemberLoanProposalCreate,
  MemberLoanSignatureMeaning,
  MemberLoanSigningCompletion,
  MemberLoanSigningDocument,
  MemberLoanSigningRequest,
  MemberLoanStatement,
  MemberLoanSummary,
} from "../types/memberLoan";
import { deviceToday, memberLoanErrorMessage } from "../utils/memberLoanText";

/**
 * The Member Loan page's state. It holds what the server computed and never
 * computes a figure itself. "Today" is always the device's date (D3).
 *
 * Every change and every statement is signed (tasks/todo/MemberLoanSigning.md):
 * `beginChangeSigning` / `beginReversalSigning` / `beginDocumentSigning` pin the
 * document in a signing request, the signing panel walks the member through it,
 * and `completeSigning` asks for the passkey (whose challenge the server bound
 * to the document) and submits the signature.
 */
export const useMemberLoanStore = defineStore("memberLoan", () => {
  const access = ref<MemberLoanAccess | null>(null);
  const accessRefusedMessage = ref<string | null>(null);
  const asOfDate = ref<string>(deviceToday());
  const summary = ref<MemberLoanSummary | null>(null);
  const ledgerRows = ref<MemberLoanLedgerRow[]>([]);
  const proposals = ref<MemberLoanProposal[]>([]);
  const statement = ref<MemberLoanStatement | null>(null);
  const auditEntries = ref<MemberLoanAuditEntry[]>([]);
  const integrity = ref<MemberLoanIntegrity | null>(null);
  const explanationLines = ref<string[]>([]);
  const errorMessage = ref<string | null>(null);
  const noticeMessage = ref<string | null>(null);
  const busyKey = ref<string | null>(null);
  const documents = ref<MemberLoanSigningDocument[]>([]);
  const activeSigningRequest = ref<MemberLoanSigningRequest | null>(null);
  const signingErrorMessage = ref<string | null>(null);

  const proposalsWaitingForMe = computed(() => proposals.value.filter((p) => p.state === "pending" && p.caller_may_sign_or_reject));
  const statementDocumentsWaitingForMe = computed(() =>
    documents.value.filter((d) => d.document_kind === "monthly_statement" && d.caller_must_act),
  );
  const proposalsWaitingForOtherMember = computed(() => proposals.value.filter((p) => p.state === "pending" && p.caller_may_cancel));
  const decidedProposals = computed(() => proposals.value.filter((p) => p.state !== "pending"));

  async function loadAccess(): Promise<boolean> {
    try {
      access.value = await memberLoanApi.access();
      accessRefusedMessage.value = null;
      return true;
    } catch (error) {
      access.value = null;
      accessRefusedMessage.value = memberLoanErrorMessage(error);
      return false;
    }
  }

  async function guarded<T>(key: string, action: () => Promise<T>): Promise<T | undefined> {
    busyKey.value = key;
    errorMessage.value = null;
    try {
      return await action();
    } catch (error) {
      errorMessage.value = memberLoanErrorMessage(error);
      return undefined;
    } finally {
      busyKey.value = null;
    }
  }

  const loadSummary = (date: string = asOfDate.value) =>
    guarded("summary", async () => {
      asOfDate.value = date;
      summary.value = await memberLoanApi.summary(date);
    });
  const loadLedger = () => guarded("ledger", async () => {
    ledgerRows.value = await memberLoanApi.ledger(deviceToday());
  });
  const loadProposals = () => guarded("proposals", async () => {
    proposals.value = await memberLoanApi.proposals();
  });
  const loadStatement = (month: string) => guarded("statement", async () => {
    statement.value = await memberLoanApi.statement(month);
  });
  const loadAudit = () => guarded("audit", async () => {
    [auditEntries.value, integrity.value] = await Promise.all([memberLoanApi.audit(), memberLoanApi.integrity()]);
  });
  const loadExplanation = () => guarded("explanation", async () => {
    explanationLines.value = await memberLoanApi.explanation();
  });
  const loadDocuments = () => guarded("documents", async () => {
    documents.value = await memberLoanApi.documents();
  });

  async function refreshAfterChange() {
    await Promise.all([loadProposals(), loadSummary(), loadAccess(), loadDocuments()]);
  }

  // -- signing ---------------------------------------------------------------------

  async function beginSigning(key: string, start: () => Promise<MemberLoanSigningRequest>): Promise<boolean> {
    signingErrorMessage.value = null;
    const signingRequest = await guarded(key, start);
    if (signingRequest) activeSigningRequest.value = signingRequest;
    return Boolean(signingRequest);
  }

  const beginChangeSigning = (body: MemberLoanProposalCreate) => beginSigning("propose", () => memberLoanApi.startChangeSigning(body));
  const beginReversalSigning = (proposal: MemberLoanProposal, reason: string) =>
    beginSigning(`reverse:${proposal.id}`, () => memberLoanApi.startReversalSigning(proposal.id, reason));
  const beginDocumentSigning = (documentId: string, meaning: MemberLoanSignatureMeaning = "signed", objectionReason?: string) =>
    beginSigning(`sign:${documentId}`, () => memberLoanApi.startDocumentSigning(documentId, meaning, objectionReason));

  function cancelSigning() {
    activeSigningRequest.value = null;
    signingErrorMessage.value = null;
  }

  async function completeSigning(steps: {
    typedFullLegalName: string;
    electronicSignatureConsentConfirmed: boolean;
    drawnSignaturePngBase64: string;
  }): Promise<MemberLoanSigningCompletion | undefined> {
    const signingRequest = activeSigningRequest.value;
    if (!signingRequest) return undefined;
    busyKey.value = "signing";
    signingErrorMessage.value = null;
    try {
      const passkey = await memberLoanApi.signingPasskeyOptions(signingRequest.signing_request_id);
      const credential = await startAuthentication({ optionsJSON: JSON.parse(passkey.options) });
      const completion = await memberLoanApi.submitSignature(signingRequest.signing_request_id, {
        typed_full_legal_name: steps.typedFullLegalName,
        electronic_signature_consent_confirmed: steps.electronicSignatureConsentConfirmed,
        drawn_signature_png_base64: steps.drawnSignaturePngBase64,
        passkey_challenge_id: passkey.passkey_challenge_id,
        passkey_credential: credential,
      });
      activeSigningRequest.value = null;
      noticeMessage.value = signedNotice(signingRequest, completion);
      await refreshAfterChange();
      return completion;
    } catch (error) {
      signingErrorMessage.value = memberLoanErrorMessage(error);
      return undefined;
    } finally {
      busyKey.value = null;
    }
  }

  function signedNotice(signingRequest: MemberLoanSigningRequest, completion: MemberLoanSigningCompletion): string {
    const other = access.value?.other_member_display_name ?? "the other member";
    if (signingRequest.signing_purpose !== "sign_document") {
      return `Signed and sent to ${other}. Nothing changes until ${other} signs it too.`;
    }
    if (completion.document.document_kind === "loan_change") {
      return "Signed. The change is now part of the loan, and the signed copy is on its way to all three e-mail addresses and the Drive.";
    }
    const verb = signingRequest.signature_meaning === "objected" ? "Your objection was signed and recorded." : "Signed.";
    return completion.document.is_complete
      ? `${verb} Both members have now responded; the signed statement is on its way to all three e-mail addresses and the Drive.`
      : `${verb} ${other} still has to respond.`;
  }

  async function reject(proposal: MemberLoanProposal, reason: string): Promise<boolean> {
    const rejected = await guarded(`reject:${proposal.id}`, () => memberLoanApi.reject(proposal.id, reason));
    if (rejected) {
      noticeMessage.value = "Rejected. Nothing changed.";
      await refreshAfterChange();
    }
    return Boolean(rejected);
  }

  async function cancel(proposal: MemberLoanProposal): Promise<boolean> {
    const cancelled = await guarded(`cancel:${proposal.id}`, () => memberLoanApi.cancel(proposal.id));
    if (cancelled) {
      noticeMessage.value = "Cancelled. Nothing changed.";
      await refreshAfterChange();
    }
    return Boolean(cancelled);
  }

  function saveBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const downloadStatementPdf = (month: string) =>
    guarded("pdf", async () => saveBlob(await memberLoanApi.statementPdf(month), `member-loan-statement-${month}.pdf`));
  const downloadSigningRequestPdf = () =>
    guarded("signing-pdf", async () => {
      const signingRequest = activeSigningRequest.value;
      if (signingRequest) saveBlob(await memberLoanApi.signingRequestPdf(signingRequest.signing_request_id), "member-loan-document-to-sign.pdf");
    });
  const downloadDocumentPdf = (document: MemberLoanSigningDocument) =>
    guarded(`document-pdf:${document.id}`, async () => saveBlob(await memberLoanApi.documentPdf(document.id), `${document.title}.pdf`));
  const downloadSignedCopyPdf = (documentId: string, title: string) =>
    guarded(`signed-pdf:${documentId}`, async () => saveBlob(await memberLoanApi.signedCopyPdf(documentId), `${title} - signed.pdf`));
  const downloadLedgerCsv = () =>
    guarded("csv", async () => {
      const today = deviceToday();
      saveBlob(await memberLoanApi.ledgerCsv(today), `member-loan-ledger-through-${today}.csv`);
    });

  return {
    access,
    accessRefusedMessage,
    asOfDate,
    summary,
    ledgerRows,
    proposals,
    statement,
    auditEntries,
    integrity,
    explanationLines,
    errorMessage,
    noticeMessage,
    busyKey,
    documents,
    activeSigningRequest,
    signingErrorMessage,
    statementDocumentsWaitingForMe,
    proposalsWaitingForMe,
    proposalsWaitingForOtherMember,
    decidedProposals,
    loadAccess,
    loadSummary,
    loadLedger,
    loadProposals,
    loadStatement,
    loadAudit,
    loadExplanation,
    loadDocuments,
    beginChangeSigning,
    beginReversalSigning,
    beginDocumentSigning,
    cancelSigning,
    completeSigning,
    reject,
    cancel,
    downloadStatementPdf,
    downloadSigningRequestPdf,
    downloadDocumentPdf,
    downloadSignedCopyPdf,
    downloadLedgerCsv,
  };
});
