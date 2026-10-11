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
  MemberLoanStatement,
  MemberLoanSummary,
} from "../types/memberLoan";
import { deviceToday, memberLoanErrorMessage } from "../utils/memberLoanText";

/**
 * The Member Loan page's state. It holds what the server computed and never
 * computes a figure itself. "Today" is always the device's date (D3).
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

  const proposalsWaitingForMe = computed(() => proposals.value.filter((p) => p.state === "pending" && p.caller_may_approve_or_reject));
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

  async function refreshAfterChange() {
    await Promise.all([loadProposals(), loadSummary(), loadAccess()]);
  }

  function replaceProposal(updated: MemberLoanProposal) {
    const index = proposals.value.findIndex((p) => p.id === updated.id);
    if (index >= 0) proposals.value.splice(index, 1, updated);
    else proposals.value.unshift(updated);
  }

  async function propose(body: MemberLoanProposalCreate): Promise<MemberLoanProposal | undefined> {
    const created = await guarded("propose", () => memberLoanApi.propose(body));
    if (created) {
      noticeMessage.value = `Sent to ${access.value?.other_member_display_name ?? "the other member"} for approval. Nothing changes until they approve it.`;
      await refreshAfterChange();
    }
    return created;
  }

  async function approve(proposal: MemberLoanProposal): Promise<boolean> {
    const fingerprint = proposal.live_preview?.preview_fingerprint;
    if (!fingerprint) {
      errorMessage.value = proposal.live_preview_problem ?? "This change cannot be approved as things stand.";
      return false;
    }
    const approved = await guarded(`approve:${proposal.id}`, () => memberLoanApi.approve(proposal.id, fingerprint));
    if (!approved) {
      // "figures_changed": show the new figures before the member tries again.
      const fresh = await memberLoanApi.proposal(proposal.id).catch(() => null);
      if (fresh) replaceProposal(fresh);
      return false;
    }
    noticeMessage.value = "Approved. The change is now part of the loan.";
    await refreshAfterChange();
    return true;
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

  async function proposeReversal(proposal: MemberLoanProposal, reason: string): Promise<boolean> {
    const reversal = await guarded(`reverse:${proposal.id}`, () => memberLoanApi.proposeReversal(proposal.id, reason));
    if (reversal) {
      noticeMessage.value = `The reversal was sent to ${access.value?.other_member_display_name ?? "the other member"} for approval.`;
      await refreshAfterChange();
    }
    return Boolean(reversal);
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
    propose,
    approve,
    reject,
    cancel,
    proposeReversal,
    downloadStatementPdf,
    downloadLedgerCsv,
  };
});
