<script setup lang="ts">
/**
 * One proposed change: what it is, who proposed it, the before → after figures,
 * and what the viewer may do. Signing its Loan Change Record (which approves it)
 * and rejecting are for the other member only, cancelling for the proposer (the
 * server enforces both). Signing asks for the passkey over the document itself;
 * rejecting and cancelling through the API's step-up answer.
 */
import { computed, ref } from "vue";

import type { MemberLoanProposal } from "../../types/memberLoan";
import { PROPOSAL_STATE_LABELS, formatLoanDate, formatLoanMoney } from "../../utils/memberLoanText";
import MemberLoanBucketsTable from "./MemberLoanBucketsTable.vue";

const props = defineProps<{ proposal: MemberLoanProposal; busy?: boolean; highlighted?: boolean; lenderName?: string; yardenName?: string }>();
const emit = defineEmits<{ sign: []; reject: [reason: string]; cancel: []; reverse: [reason: string]; downloadSignedCopy: [] }>();

const rejecting = ref(false);
const rejectionReason = ref("");
const reversing = ref(false);
const reversalReason = ref("");

const preview = computed(() => props.proposal.live_preview ?? props.proposal.preview_at_proposal);
type BadgeTone = "neutral" | "warning" | "positive" | "negative";
const TONE_BY_STATE: Record<MemberLoanProposal["state"], BadgeTone> = {
  pending: "warning",
  approved: "positive",
  rejected: "negative",
  cancelled: "neutral",
  expired: "neutral",
};
const stateTone = computed(() => TONE_BY_STATE[props.proposal.state]);
const interestChoiceText = computed(() =>
  props.proposal.interest_election_choice === "cash" ? "Pay the month's interest in cash" : "Add the month's interest to the debt",
);

function submitRejection() {
  if (!rejectionReason.value.trim()) return;
  emit("reject", rejectionReason.value.trim());
}

function submitReversal() {
  if (reversalReason.value.trim().length < 3) return;
  emit("reverse", reversalReason.value.trim());
}
</script>

<template>
  <article
    :id="`proposal-${proposal.id}`"
    class="flex flex-col gap-3 rounded-card border bg-surface p-4"
    :class="highlighted ? 'border-primary ring-2 ring-primary/30' : 'border-line'"
    data-testid="member-loan.proposal"
    :data-state="proposal.state"
    :data-event-type="proposal.event_type"
  >
    <header class="flex flex-wrap items-start justify-between gap-2">
      <div class="min-w-0">
        <h3 class="text-base font-semibold text-fg">
          {{ proposal.plain_event_name }}<template v-if="proposal.amount"> of {{ formatLoanMoney(proposal.amount) }}</template>
        </h3>
        <p class="text-sm text-fg-muted">
          <template v-if="proposal.event_type === 'interest_payment_election'">{{ interestChoiceText }} on {{ formatLoanDate(proposal.effective_date) }}</template>
          <template v-else>Takes effect on {{ formatLoanDate(proposal.effective_date) }}</template>
        </p>
      </div>
      <UiBadge :tone="stateTone" data-testid="member-loan.proposal-state">{{ PROPOSAL_STATE_LABELS[proposal.state] }}</UiBadge>
    </header>

    <ul class="flex flex-col gap-0.5 text-sm text-fg-muted">
      <li v-if="proposal.reversed_event_summary">It reverses: {{ proposal.reversed_event_summary }}</li>
      <li v-if="proposal.reversal_reason">Reason: {{ proposal.reversal_reason }}</li>
      <li v-if="proposal.written_agreement_date">
        Written agreement of {{ formatLoanDate(proposal.written_agreement_date) }}: “{{ proposal.written_agreement_description }}”
      </li>
      <li v-if="proposal.payment_reference">Payment reference: {{ proposal.payment_reference }}</li>
      <li v-if="proposal.note">Note: {{ proposal.note }}</li>
      <li>Proposed by {{ proposal.proposed_by_display_name }} on {{ formatLoanDate(proposal.proposed_at) }}</li>
      <li v-if="proposal.decided_by_display_name">
        {{ PROPOSAL_STATE_LABELS[proposal.state] }} by {{ proposal.decided_by_display_name }} on {{ formatLoanDate(proposal.decided_at) }}<template
          v-if="proposal.decision_reason"
        >: {{ proposal.decision_reason }}</template>
      </li>
    </ul>

    <p
      v-if="proposal.includes_yarden_increase_warning"
      class="rounded-ctl border border-warning/50 bg-warning/10 p-2 text-sm text-fg"
      data-testid="member-loan.no-clause-warning"
    >
      This change increases the loan under Section 7A of the Agreement (Amendment No. 1). It relies on the written agreement cited above.
    </p>
    <p v-if="proposal.live_preview_problem" class="rounded-ctl border border-negative/40 bg-negative/10 p-2 text-sm text-fg" role="alert">
      {{ proposal.live_preview_problem }}
    </p>

    <div v-if="proposal.event_type !== 'interest_payment_election'">
      <p class="mb-1 text-xs uppercase tracking-wide text-fg-muted">
        {{ proposal.state === "pending" ? `If approved, on ${formatLoanDate(preview.effective_date)}` : `On ${formatLoanDate(preview.effective_date)}` }}
      </p>
      <MemberLoanBucketsTable :before="preview.buckets_before" :after="preview.buckets_after" />
    </div>

    <div v-if="proposal.caller_may_sign_or_reject" class="flex flex-col gap-2">
      <div class="flex flex-wrap gap-2">
        <UiButton
          variant="primary"
          :loading="busy"
          :disabled="busy || !proposal.live_preview || !proposal.signing_document_id"
          data-testid="member-loan.sign-open"
          @click="emit('sign')"
        >
          <i class="pi pi-pen-to-square" aria-hidden="true" /> Review and sign
        </UiButton>
        <UiButton variant="secondary" :disabled="busy" data-testid="member-loan.reject-open" @click="rejecting = !rejecting">Reject…</UiButton>
      </div>
      <form v-if="rejecting" class="flex flex-col gap-2 sm:flex-row" @submit.prevent="submitRejection">
        <label class="sr-only" :for="`reject-reason-${proposal.id}`">Why are you rejecting it?</label>
        <input
          :id="`reject-reason-${proposal.id}`"
          v-model="rejectionReason"
          maxlength="500"
          required
          placeholder="Why are you rejecting it?"
          class="flex-1 rounded-ctl border border-line bg-page px-3 py-2 text-sm text-fg"
          data-testid="member-loan.reject-reason"
        />
        <UiButton type="submit" variant="danger" :disabled="busy || !rejectionReason.trim()" data-testid="member-loan.reject">Reject</UiButton>
      </form>
      <p class="text-xs text-fg-muted">Signing its Loan Change Record approves the change. Signing and rejecting ask for your passkey.</p>
    </div>

    <div v-if="proposal.caller_may_cancel" class="flex flex-wrap items-center gap-2">
      <UiButton variant="secondary" :disabled="busy" data-testid="member-loan.cancel" @click="emit('cancel')">Cancel this proposal</UiButton>
      <span class="text-xs text-fg-muted">You signed it. Waiting for the other member to sign it too.</span>
    </div>

    <div v-if="proposal.state === 'approved' && proposal.signing_document_id">
      <UiButton variant="ghost" size="sm" :disabled="busy" data-testid="member-loan.signed-copy" @click="emit('downloadSignedCopy')">
        <i class="pi pi-file-pdf" aria-hidden="true" /> Signed Loan Change Record (PDF)
      </UiButton>
    </div>

    <div v-if="proposal.caller_may_propose_reversal" class="flex flex-col gap-2">
      <button type="button" class="self-start text-xs text-fg-muted underline-offset-2 hover:underline" data-testid="member-loan.reverse-open" @click="reversing = !reversing">
        Propose a reversal…
      </button>
      <form v-if="reversing" class="flex flex-col gap-2 sm:flex-row" @submit.prevent="submitReversal">
        <label class="sr-only" :for="`reverse-reason-${proposal.id}`">Why should it be reversed?</label>
        <input
          :id="`reverse-reason-${proposal.id}`"
          v-model="reversalReason"
          maxlength="500"
          required
          placeholder="Why should it be reversed?"
          class="flex-1 rounded-ctl border border-line bg-page px-3 py-2 text-sm text-fg"
          data-testid="member-loan.reverse-reason"
        />
        <UiButton type="submit" variant="secondary" :disabled="busy || reversalReason.trim().length < 3" data-testid="member-loan.reverse">
          Review and sign the reversal
        </UiButton>
      </form>
    </div>
  </article>
</template>
