<script setup lang="ts">
/**
 * The Member Loan between Aviv (Lender) and Big Whales AY LLC.
 *
 * Only the two members can open it (the API checks the passkey session and the
 * member list; this page only mirrors that). Every figure comes from the
 * server; "today" is this device's date. A change is proposed by one member
 * and takes effect only when the other approves it. `/member-loan/approvals/:eventId`
 * is the link the approval e-mail carries: it opens the "Waiting" tab on that change.
 */
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import MemberLoanBucketsTable from "../components/memberLoan/MemberLoanBucketsTable.vue";
import MemberLoanProposalCard from "../components/memberLoan/MemberLoanProposalCard.vue";
import MemberLoanProposeForm from "../components/memberLoan/MemberLoanProposeForm.vue";
import MemberLoanStatementPanel from "../components/memberLoan/MemberLoanStatementPanel.vue";
import { useAuthStore } from "../stores/authStore";
import { useMemberLoanStore } from "../stores/memberLoanStore";
import type { MemberLoanProposal, MemberLoanProposalCreate } from "../types/memberLoan";
import { deviceToday, formatLoanDate, formatLoanMoney, formatLoanMonth, loanStatementMonths } from "../utils/memberLoanText";

const props = defineProps<{ eventId?: string }>();

type TabKey = "today" | "waiting" | "history" | "propose" | "statements" | "how" | "audit";
const TABS: { key: TabKey; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "waiting", label: "Waiting for approval" },
  { key: "history", label: "History" },
  { key: "propose", label: "Propose a change" },
  { key: "statements", label: "Statements" },
  { key: "how", label: "How it works" },
  { key: "audit", label: "Audit trail" },
];
const AUDIT_ACTION_LABELS: Record<string, string> = {
  event_proposed: "Proposed a change",
  event_approved: "Approved a change",
  event_rejected: "Rejected a change",
  event_cancelled: "Cancelled a proposal",
  event_expired: "A proposal expired",
  proposal_notification_sent: "E-mailed the proposal",
  proposal_notification_failed: "Could not e-mail the proposal",
  decision_notification_sent: "E-mailed the decision",
  decision_notification_failed: "Could not e-mail the decision",
  statement_sent: "Sent the monthly statement",
  statement_dry_run: "Prepared a statement (test run, not sent)",
  statement_send_failed: "Could not send the monthly statement",
};

const auth = useAuthStore();
const loan = useMemberLoanStore();
const route = useRoute();
const router = useRouter();

const ready = ref(false);
const activeTab = ref<TabKey>("today");
const statementMonth = ref<string>("");
const highlightedProposalId = ref<string | null>(props.eventId ?? null);

const lenderName = computed(() => (loan.access?.role === "lender" ? loan.access.display_name : loan.access?.other_member_display_name) ?? "Aviv");
const yardenName = computed(() => (loan.access?.role === "yarden" ? loan.access.display_name : loan.access?.other_member_display_name) ?? "Yarden");
const statementMonths = computed(() => loanStatementMonths("2026-10", deviceToday().slice(0, 7)));
const waitingCount = computed(() => loan.proposalsWaitingForMe.length);

function selectTab(tab: TabKey) {
  activeTab.value = tab;
  const query: Record<string, string> = { ...(route.query as Record<string, string>), tab };
  if (tab !== "statements") delete query.month;
  void router.replace({ name: "member-loan", query });
}

async function loadTab(tab: TabKey) {
  if (tab === "today") await loan.loadSummary();
  if (tab === "waiting") await loan.loadProposals();
  if (tab === "history") await Promise.all([loan.loadLedger(), loan.loadProposals()]);
  if (tab === "statements" && statementMonth.value) await loan.loadStatement(statementMonth.value);
  if (tab === "how") await loan.loadExplanation();
  if (tab === "audit") await loan.loadAudit();
}

watch(activeTab, (tab) => {
  if (ready.value) void loadTab(tab);
});
watch(statementMonth, (month) => {
  if (ready.value && month) {
    void loan.loadStatement(month);
    void router.replace({ name: "member-loan", query: { tab: "statements", month } });
  }
});

async function onPropose(body: MemberLoanProposalCreate) {
  const created = await loan.propose(body);
  if (created) {
    highlightedProposalId.value = created.id;
    selectTab("waiting");
  }
}

async function onApprove(proposal: MemberLoanProposal) {
  await loan.approve(proposal);
}

async function onReject(proposal: MemberLoanProposal, reason: string) {
  await loan.reject(proposal, reason);
}

async function onCancel(proposal: MemberLoanProposal) {
  if (!window.confirm("Cancel this proposal? Nothing will change.")) return;
  await loan.cancel(proposal);
}

async function onReverse(proposal: MemberLoanProposal, reason: string) {
  await loan.proposeReversal(proposal, reason);
}

async function changeAsOfDate(event: Event) {
  const value = (event.target as HTMLInputElement).value;
  if (value) await loan.loadSummary(value);
}

onMounted(async () => {
  if (auth.status === "unknown") await auth.load();
  if (auth.status === "pending") {
    await router.replace("/pending");
    return;
  }
  if (auth.status !== "trusted") {
    await router.replace({ name: "login", query: { next: route.fullPath } });
    return;
  }
  if (!(await loan.loadAccess())) {
    ready.value = true;
    return;
  }
  const requestedTab = route.query.tab as TabKey | undefined;
  activeTab.value = props.eventId ? "waiting" : TABS.some((t) => t.key === requestedTab) ? requestedTab! : "today";
  statementMonth.value = (route.query.month as string) || statementMonths.value[1] || statementMonths.value[0]!;
  ready.value = true;
  await Promise.all([loadTab(activeTab.value), loan.loadProposals(), activeTab.value === "today" ? null : loan.loadSummary()]);
  if (highlightedProposalId.value) {
    await nextTick();
    document.getElementById(`proposal-${highlightedProposalId.value}`)?.scrollIntoView({ block: "center" });
  }
});
</script>

<template>
  <section class="mx-auto flex w-full max-w-5xl flex-col gap-6 p-4 sm:p-6" data-testid="member-loan.page">
    <div>
      <p class="text-xs uppercase tracking-wide text-fg-muted">Big Whales AY LLC</p>
      <h1 class="text-2xl font-semibold text-fg">Member Loan</h1>
      <p class="text-sm text-fg-muted">The loan from Aviv Jan to the company. Every change needs both members.</p>
    </div>

    <p v-if="ready && loan.accessRefusedMessage" class="rounded-ctl border border-negative/40 bg-negative/10 p-3 text-sm text-fg" role="alert" data-testid="member-loan.refused">
      {{ loan.accessRefusedMessage }}
    </p>

    <template v-if="ready && loan.access">
      <UiTabs aria-label="Member Loan sections" class="max-w-full">
        <UiButton
          v-for="tab in TABS"
          :key="tab.key"
          variant="tab"
          size="sm"
          role="tab"
          :active="activeTab === tab.key"
          :aria-selected="activeTab === tab.key"
          :data-testid="`member-loan.tab-${tab.key}`"
          @click="selectTab(tab.key)"
        >
          {{ tab.label }}
          <span v-if="tab.key === 'waiting' && waitingCount" class="ml-1 rounded-full bg-primary px-1.5 text-[11px] text-primary-fg" data-testid="member-loan.waiting-count">{{ waitingCount }}</span>
        </UiButton>
      </UiTabs>

      <p v-if="loan.noticeMessage" class="rounded-ctl border border-positive/40 bg-positive/10 p-3 text-sm text-fg" role="status" data-testid="member-loan.notice">
        {{ loan.noticeMessage }}
      </p>
      <p v-if="loan.errorMessage" class="rounded-ctl border border-negative/40 bg-negative/10 p-3 text-sm text-fg" role="alert" data-testid="member-loan.error">
        {{ loan.errorMessage }}
      </p>

      <!-- Today -->
      <div v-if="activeTab === 'today'" class="flex flex-col gap-4" data-testid="member-loan.today">
        <div class="flex flex-wrap items-end gap-3">
          <div class="flex flex-col gap-1">
            <label for="member-loan-as-of" class="text-sm font-medium text-fg">As of</label>
            <input id="member-loan-as-of" type="date" :value="loan.asOfDate" min="2026-10-01" class="rounded-ctl border border-line bg-page px-3 py-2 text-fg" data-testid="member-loan.as-of" @change="changeAsOfDate" />
          </div>
          <p v-if="loan.summary?.proposals_waiting_for_you" class="text-sm text-primary">
            {{ loan.summary.proposals_waiting_for_you }} change{{ loan.summary.proposals_waiting_for_you === 1 ? " is" : "s are" }} waiting for your approval.
          </p>
        </div>
        <template v-if="loan.summary">
          <UiKpiCard label="Amount Owed" :value="formatLoanMoney(loan.summary.buckets.amount_owed)" icon="pi pi-wallet" data-testid="member-loan.amount-owed" />
          <UiCard padding="md">
            <h2 class="mb-2 text-sm font-semibold text-fg">How it is made up on {{ formatLoanDate(loan.summary.as_of_date) }}</h2>
            <MemberLoanBucketsTable :after="loan.summary.buckets" show-capital-credited :lender-name="lenderName" />
            <p class="mt-3 text-xs text-fg-muted">
              Started {{ formatLoanDate(loan.summary.loan_effective_date) }} with {{ formatLoanMoney(loan.summary.original_principal_at_start) }}. Due
              {{ formatLoanDate(loan.summary.maturity_date) }}; interest keeps running until it is repaid.
            </p>
          </UiCard>
        </template>
      </div>

      <!-- Waiting for approval -->
      <div v-if="activeTab === 'waiting'" class="flex flex-col gap-6" data-testid="member-loan.waiting">
        <div class="flex flex-col gap-3">
          <h2 class="text-base font-semibold text-fg">Waiting for you</h2>
          <UiEmptyState v-if="!loan.proposalsWaitingForMe.length">Nothing is waiting for your approval.</UiEmptyState>
          <MemberLoanProposalCard
            v-for="proposal in loan.proposalsWaitingForMe"
            :key="proposal.id"
            :proposal="proposal"
            :highlighted="proposal.id === highlightedProposalId"
            :busy="loan.busyKey !== null"
            @approve="onApprove(proposal)"
            @reject="(reason) => onReject(proposal, reason)"
          />
        </div>
        <div class="flex flex-col gap-3">
          <h2 class="text-base font-semibold text-fg">Waiting for {{ loan.access.other_member_display_name }}</h2>
          <UiEmptyState v-if="!loan.proposalsWaitingForOtherMember.length">You have no proposals waiting.</UiEmptyState>
          <MemberLoanProposalCard
            v-for="proposal in loan.proposalsWaitingForOtherMember"
            :key="proposal.id"
            :proposal="proposal"
            :highlighted="proposal.id === highlightedProposalId"
            :busy="loan.busyKey !== null"
            @cancel="onCancel(proposal)"
          />
        </div>
      </div>

      <!-- History -->
      <div v-if="activeTab === 'history'" class="flex flex-col gap-6" data-testid="member-loan.history">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <h2 class="text-base font-semibold text-fg">Every change, in date order</h2>
          <UiButton variant="secondary" size="sm" :loading="loan.busyKey === 'csv'" data-testid="member-loan.csv" @click="loan.downloadLedgerCsv()">
            <i class="pi pi-download" aria-hidden="true" /> Download CSV
          </UiButton>
        </div>
        <!-- Focusable so a keyboard can scroll it sideways on a phone (axe: scrollable-region-focusable). -->
        <div class="overflow-x-auto rounded-ctl border border-line focus:outline-none focus:ring-2 focus:ring-primary/50" tabindex="0" role="region" aria-label="Loan history table">
          <table class="w-full min-w-[56rem] text-sm" data-testid="member-loan.ledger">
            <thead class="bg-surface-muted text-xs text-fg-muted">
              <tr>
                <th class="px-3 py-2 text-left font-medium">Date</th>
                <th class="px-3 py-2 text-left font-medium">What happened</th>
                <th class="px-3 py-2 text-right font-medium">Principal</th>
                <th class="px-3 py-2 text-right font-medium">Capitalized interest</th>
                <th class="px-3 py-2 text-right font-medium">Total Balance</th>
                <th class="px-3 py-2 text-right font-medium">Accrued interest</th>
                <th class="px-3 py-2 text-right font-medium">Amount Owed</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in loan.ledgerRows" :key="`${row.row_date}-${row.row_kind}-${index}`" class="border-t border-line/60" data-testid="member-loan.ledger-row" :data-kind="row.row_kind">
                <td class="whitespace-nowrap px-3 py-2 text-fg-muted">{{ formatLoanDate(row.row_date) }}</td>
                <td class="px-3 py-2 text-fg">
                  {{ row.plain_description }}
                  <span v-if="row.approved_by_display_name" class="block text-xs text-fg-muted">
                    Proposed by {{ row.proposed_by_display_name }}, approved by {{ row.approved_by_display_name }}
                  </span>
                </td>
                <td class="px-3 py-2 text-right tabular-nums">{{ formatLoanMoney(row.buckets_after.original_principal) }}</td>
                <td class="px-3 py-2 text-right tabular-nums">{{ formatLoanMoney(row.buckets_after.capitalized_interest) }}</td>
                <td class="px-3 py-2 text-right font-semibold tabular-nums">{{ formatLoanMoney(row.buckets_after.total_balance) }}</td>
                <td class="px-3 py-2 text-right tabular-nums">{{ formatLoanMoney(row.buckets_after.accrued_interest) }}</td>
                <td class="px-3 py-2 text-right tabular-nums">{{ formatLoanMoney(row.buckets_after.amount_owed) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="flex flex-col gap-3">
          <h2 class="text-base font-semibold text-fg">Decided proposals</h2>
          <UiEmptyState v-if="!loan.decidedProposals.length">No decisions yet.</UiEmptyState>
          <MemberLoanProposalCard
            v-for="proposal in loan.decidedProposals"
            :key="proposal.id"
            :proposal="proposal"
            :busy="loan.busyKey !== null"
            @reverse="(reason) => onReverse(proposal, reason)"
          />
        </div>
      </div>

      <!-- Propose -->
      <UiCard v-if="activeTab === 'propose'" padding="md" data-testid="member-loan.propose">
        <MemberLoanProposeForm
          :lender-name="lenderName"
          :yarden-name="yardenName"
          :other-member-name="loan.access.other_member_display_name"
          :busy="loan.busyKey === 'propose'"
          @submit="onPropose"
        />
      </UiCard>

      <!-- Statements -->
      <div v-if="activeTab === 'statements'" class="flex flex-col gap-4" data-testid="member-loan.statements">
        <div class="flex flex-wrap items-end gap-3">
          <div class="flex flex-col gap-1">
            <label for="member-loan-statement-month" class="text-sm font-medium text-fg">Month</label>
            <select id="member-loan-statement-month" v-model="statementMonth" class="rounded-ctl border border-line bg-page px-3 py-2 text-fg" data-testid="member-loan.statement-month">
              <option v-for="month in statementMonths" :key="month" :value="month">{{ formatLoanMonth(month) }}</option>
            </select>
          </div>
          <UiButton variant="secondary" size="sm" :loading="loan.busyKey === 'pdf'" data-testid="member-loan.pdf" @click="loan.downloadStatementPdf(statementMonth)">
            <i class="pi pi-file-pdf" aria-hidden="true" /> Download PDF
          </UiButton>
        </div>
        <UiCard v-if="loan.statement" padding="md">
          <MemberLoanStatementPanel :statement="loan.statement" />
        </UiCard>
      </div>

      <!-- How it works -->
      <UiCard v-if="activeTab === 'how'" padding="md" data-testid="member-loan.how">
        <h2 class="mb-3 text-base font-semibold text-fg">How the loan is calculated</h2>
        <ul class="list-disc space-y-2 pl-5 text-sm text-fg">
          <li v-for="line in loan.explanationLines" :key="line">{{ line }}</li>
        </ul>
      </UiCard>

      <!-- Audit -->
      <div v-if="activeTab === 'audit'" class="flex flex-col gap-3" data-testid="member-loan.audit">
        <p
          v-if="loan.integrity"
          class="rounded-ctl border p-3 text-sm text-fg"
          :class="loan.integrity.intact ? 'border-positive/40 bg-positive/10' : 'border-negative/40 bg-negative/10'"
          data-testid="member-loan.integrity"
        >
          <template v-if="loan.integrity.intact">
            The history is intact: {{ loan.integrity.proposals_checked }} proposals, {{ loan.integrity.decisions_checked }} decisions and
            {{ loan.integrity.audit_entries_checked }} audit entries checked.
          </template>
          <template v-else>Warning: the history was changed outside the app. {{ loan.integrity.problems.join(" ") }}</template>
        </p>
        <ul class="flex flex-col gap-2" role="list">
          <li v-for="entry in loan.auditEntries" :key="entry.audit_sequence" class="rounded-ctl border border-line bg-surface p-3 text-sm" data-testid="member-loan.audit-entry">
            <div class="flex flex-wrap justify-between gap-2">
              <strong class="text-fg">{{ AUDIT_ACTION_LABELS[entry.action] ?? entry.action }}</strong>
              <span class="text-xs text-fg-muted">{{ entry.actor_display_name }} · {{ new Date(entry.recorded_at).toLocaleString() }}</span>
            </div>
            <p v-if="entry.state_before && entry.state_after" class="text-xs text-fg-muted">
              Amount Owed {{ formatLoanMoney(entry.state_before.amount_owed) }} → {{ formatLoanMoney(entry.state_after.amount_owed) }}
            </p>
            <p v-if="entry.detail?.reason" class="text-xs text-fg-muted">Reason: {{ entry.detail.reason }}</p>
            <p v-if="entry.detail?.error" class="text-xs text-negative">Error: {{ entry.detail.error }}</p>
          </li>
        </ul>
      </div>
    </template>
  </section>
</template>
