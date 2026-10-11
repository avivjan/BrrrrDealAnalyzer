<script setup lang="ts">
/**
 * Propose a change. Step 1 "Check the figures" asks the server for the before →
 * after preview (nothing is saved); step 2 sends it to the other member, who
 * must approve it before anything changes. The default date is today on this
 * device; a change may fall on any day (D15) but not in the future.
 */
import { computed, reactive, ref, watch } from "vue";

import { memberLoanApi } from "../../api/memberLoan";
import type { MemberLoanEventType, MemberLoanPreview, MemberLoanProposalCreate } from "../../types/memberLoan";
import { deviceToday, formatLoanMoney, memberLoanErrorMessage } from "../../utils/memberLoanText";
import LoanAmountInput from "./LoanAmountInput.vue";
import MemberLoanBucketsTable from "./MemberLoanBucketsTable.vue";

const props = defineProps<{ lenderName: string; yardenName: string; otherMemberName: string; busy?: boolean }>();
const emit = defineEmits<{ submit: [body: MemberLoanProposalCreate] }>();

const EVENT_TYPE_CHOICES = computed<{ value: MemberLoanEventType; label: string; help: string }[]>(() => [
  {
    value: "lender_withdrawal",
    label: `${props.lenderName} withdraws money`,
    help: "Use the day the money left the company account. It is taken from interest first, then principal.",
  },
  {
    value: "lender_additional_advance",
    label: `${props.lenderName} lends more`,
    help: "Added to principal from that day. Needs the written agreement both members signed.",
  },
  {
    value: "yarden_capital_contribution_reduction",
    label: `${props.yardenName} puts in capital`,
    help: `Reduces the debt from that day and is credited to ${props.lenderName}'s capital account.`,
  },
  {
    value: "yarden_additional_withdrawal_increase",
    label: `${props.yardenName} withdraws money`,
    help: `Increases principal from that day and is debited from ${props.lenderName}'s capital account. The signed agreement has no clause for this: it needs a separate written agreement.`,
  },
  {
    value: "interest_payment_election",
    label: "Interest choice for a month",
    help: "On the 1st, the month's interest is either added to the debt (the default) or paid in cash.",
  },
]);

const form = reactive({
  event_type: "lender_withdrawal" as MemberLoanEventType,
  effective_date: deviceToday(),
  amount: null as string | null,
  interest_election_choice: "cash" as "reinvest" | "cash",
  written_agreement_date: "",
  written_agreement_description: "",
  payment_reference: "",
  note: "",
});
const preview = ref<MemberLoanPreview | null>(null);
const previewError = ref<string | null>(null);
const checking = ref(false);

const needsAmount = computed(() => form.event_type !== "interest_payment_election");
const needsWrittenAgreement = computed(
  () => form.event_type === "lender_additional_advance" || form.event_type === "yarden_additional_withdrawal_increase",
);
const helpText = computed(() => EVENT_TYPE_CHOICES.value.find((c) => c.value === form.event_type)?.help ?? "");
const latestAllowedDate = computed(() => {
  const [year, month, day] = deviceToday().split("-").map((p) => Number.parseInt(p, 10));
  const tomorrow = new Date(Date.UTC(year!, month! - 1, day! + 1));
  return tomorrow.toISOString().slice(0, 10);
});
const formComplete = computed(
  () =>
    Boolean(form.effective_date) &&
    (!needsAmount.value || Boolean(form.amount)) &&
    (!needsWrittenAgreement.value || (Boolean(form.written_agreement_date) && form.written_agreement_description.trim().length > 0)),
);

watch(form, () => {
  preview.value = null;
  previewError.value = null;
});

function body(): MemberLoanProposalCreate {
  return {
    event_type: form.event_type,
    effective_date: form.effective_date,
    amount: needsAmount.value ? form.amount : null,
    interest_election_choice: form.event_type === "interest_payment_election" ? form.interest_election_choice : null,
    written_agreement_date: needsWrittenAgreement.value ? form.written_agreement_date : null,
    written_agreement_description: needsWrittenAgreement.value ? form.written_agreement_description.trim() : null,
    payment_reference: form.payment_reference.trim() || null,
    note: form.note.trim() || null,
  };
}

async function checkFigures() {
  checking.value = true;
  previewError.value = null;
  try {
    preview.value = await memberLoanApi.preview(body());
  } catch (error) {
    previewError.value = memberLoanErrorMessage(error);
  } finally {
    checking.value = false;
  }
}

function send() {
  emit("submit", body());
}
</script>

<template>
  <form class="flex flex-col gap-4" data-testid="member-loan.propose-form" @submit.prevent="preview ? send() : checkFigures()">
    <fieldset class="flex flex-col gap-2">
      <legend class="mb-1 text-sm font-medium text-fg">What happened?</legend>
      <label
        v-for="choice in EVENT_TYPE_CHOICES"
        :key="choice.value"
        class="flex cursor-pointer items-center gap-2 rounded-ctl border border-line px-3 py-2 text-sm text-fg"
        :class="form.event_type === choice.value && 'border-primary bg-primary/5'"
      >
        <input v-model="form.event_type" type="radio" name="member-loan-event-type" :value="choice.value" :data-testid="`member-loan.type-${choice.value}`" />
        {{ choice.label }}
      </label>
      <p class="text-xs text-fg-muted" data-testid="member-loan.type-help">{{ helpText }}</p>
    </fieldset>

    <div class="grid gap-4 sm:grid-cols-2">
      <div class="flex flex-col gap-1">
        <label for="member-loan-date" class="text-sm font-medium text-fg">
          {{ form.event_type === "interest_payment_election" ? "Interest Date (the 1st)" : "Date the money moved" }}
        </label>
        <input
          id="member-loan-date"
          v-model="form.effective_date"
          type="date"
          :max="latestAllowedDate"
          required
          class="rounded-ctl border border-line bg-page px-3 py-2 text-fg"
          data-testid="member-loan.date-input"
        />
      </div>
      <LoanAmountInput v-if="needsAmount" id="member-loan-amount" v-model="form.amount" label="Amount" />
      <fieldset v-else class="flex flex-col gap-1">
        <legend class="text-sm font-medium text-fg">The month's interest is</legend>
        <label class="flex items-center gap-2 text-sm text-fg"><input v-model="form.interest_election_choice" type="radio" value="cash" /> paid to {{ lenderName }} in cash</label>
        <label class="flex items-center gap-2 text-sm text-fg"><input v-model="form.interest_election_choice" type="radio" value="reinvest" /> added to the debt</label>
      </fieldset>
    </div>

    <div v-if="needsWrittenAgreement" class="grid gap-4 rounded-ctl border border-warning/50 bg-warning/5 p-3 sm:grid-cols-[12rem,1fr]" data-testid="member-loan.written-agreement">
      <p class="text-sm text-fg sm:col-span-2">This change needs the written agreement both members signed.</p>
      <div class="flex flex-col gap-1">
        <label for="member-loan-agreement-date" class="text-sm font-medium text-fg">Agreement date</label>
        <input id="member-loan-agreement-date" v-model="form.written_agreement_date" type="date" required class="rounded-ctl border border-line bg-page px-3 py-2 text-fg" />
      </div>
      <div class="flex flex-col gap-1">
        <label for="member-loan-agreement-description" class="text-sm font-medium text-fg">Short description</label>
        <input id="member-loan-agreement-description" v-model="form.written_agreement_description" maxlength="500" required class="rounded-ctl border border-line bg-page px-3 py-2 text-fg" placeholder="For example: side letter signed by both" />
      </div>
    </div>

    <div class="grid gap-4 sm:grid-cols-2">
      <div class="flex flex-col gap-1">
        <label for="member-loan-reference" class="text-sm font-medium text-fg">Payment reference <span class="font-normal text-fg-muted">(optional)</span></label>
        <input id="member-loan-reference" v-model="form.payment_reference" maxlength="200" class="rounded-ctl border border-line bg-page px-3 py-2 text-fg" placeholder="For example a Mercury transaction id" />
      </div>
      <div class="flex flex-col gap-1">
        <label for="member-loan-note" class="text-sm font-medium text-fg">Note <span class="font-normal text-fg-muted">(optional)</span></label>
        <input id="member-loan-note" v-model="form.note" maxlength="1000" class="rounded-ctl border border-line bg-page px-3 py-2 text-fg" />
      </div>
    </div>

    <p v-if="previewError" class="rounded-ctl border border-negative/40 bg-negative/10 p-3 text-sm text-fg" role="alert" data-testid="member-loan.preview-error">{{ previewError }}</p>

    <div v-if="preview" class="flex flex-col gap-2 rounded-ctl border border-line bg-surface-muted p-3" data-testid="member-loan.preview">
      <p class="text-sm text-fg">
        If {{ otherMemberName }} approves<template v-if="form.amount && needsAmount"> this {{ formatLoanMoney(form.amount) }} change</template>, the loan on that day becomes:
      </p>
      <MemberLoanBucketsTable :before="preview.buckets_before" :after="preview.buckets_after" />
    </div>

    <div class="flex flex-wrap items-center gap-3">
      <UiButton v-if="!preview" type="submit" variant="secondary" :loading="checking" :disabled="!formComplete || checking" data-testid="member-loan.check">
        Check the figures
      </UiButton>
      <UiButton v-else type="submit" variant="primary" :loading="busy" :disabled="busy" data-testid="member-loan.send">
        Send to {{ otherMemberName }} for approval
      </UiButton>
      <span class="text-xs text-fg-muted">Nothing changes until {{ otherMemberName }} approves it. Sending asks for your passkey.</span>
    </div>
  </form>
</template>
