// @vitest-environment jsdom
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import MemberLoan from "./MemberLoan.vue";
import SecurityBar from "../components/shell/SecurityBar.vue";
import LoanAmountInput from "../components/memberLoan/LoanAmountInput.vue";
import { memberLoanApi } from "../api/memberLoan";
import { useAuthStore } from "../stores/authStore";
import type { MemberLoanBuckets, MemberLoanPreview, MemberLoanProposal } from "../types/memberLoan";

vi.mock("../api/memberLoan", () => ({
  memberLoanApi: {
    access: vi.fn(),
    summary: vi.fn(),
    ledger: vi.fn(),
    proposals: vi.fn(),
    proposal: vi.fn(),
    preview: vi.fn(),
    propose: vi.fn(),
    proposeReversal: vi.fn(),
    approve: vi.fn(),
    reject: vi.fn(),
    cancel: vi.fn(),
    statement: vi.fn(),
    statementPdf: vi.fn(),
    ledgerCsv: vi.fn(),
    audit: vi.fn(),
    integrity: vi.fn(),
    explanation: vi.fn(),
  },
}));

const api = vi.mocked(memberLoanApi);

function buckets(amountOwed: string, overrides: Partial<MemberLoanBuckets> = {}): MemberLoanBuckets {
  return {
    original_principal: "30410.00",
    capitalized_interest: "611.24",
    total_balance: "31021.24",
    accrued_interest: "144.77",
    interest_payable: "0.00",
    amount_owed: amountOwed,
    lender_capital_credited: "0.00",
    ...overrides,
  };
}

function preview(fingerprint = "a".repeat(64)): MemberLoanPreview {
  return {
    effective_date: "2026-12-15",
    buckets_before: buckets("31166.01"),
    buckets_after: buckets("30166.01", { original_principal: "30166.01", capitalized_interest: "0.00", total_balance: "30166.01", accrued_interest: "0.00" }),
    allocation: null,
    preview_fingerprint: fingerprint,
  };
}

function proposal(overrides: Partial<MemberLoanProposal> = {}): MemberLoanProposal {
  return {
    id: "p1",
    proposal_sequence: 1,
    event_type: "lender_withdrawal",
    plain_event_name: "Withdrawal by Aviv",
    effective_date: "2026-12-15",
    amount: "1000.00",
    interest_election_choice: null,
    written_agreement_date: null,
    written_agreement_description: null,
    payment_reference: null,
    note: null,
    reverses_event_id: null,
    reversed_event_summary: null,
    reversal_reason: null,
    state: "pending",
    proposed_by_display_name: "Aviv",
    proposed_at: "2026-12-15T15:00:00+00:00",
    decided_by_display_name: null,
    decided_at: null,
    decision_reason: null,
    preview_at_proposal: preview(),
    live_preview: preview(),
    live_preview_problem: null,
    figures_changed_since_proposal: false,
    caller_may_approve_or_reject: true,
    caller_may_cancel: false,
    caller_may_propose_reversal: false,
    includes_yarden_increase_warning: false,
    ...overrides,
  };
}

async function mountPage(path = "/member-loan", { status = "trusted" as const } = {}) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/member-loan", name: "member-loan", component: MemberLoan },
      { path: "/member-loan/approvals/:eventId", name: "member-loan-approval", component: MemberLoan, props: true },
      { path: "/login", name: "login", component: { template: "<p>login</p>" } },
      { path: "/pending", name: "pending", component: { template: "<p>pending</p>" } },
    ],
  });
  await router.push(path);
  await router.isReady();
  const auth = useAuthStore();
  auth.status = status;
  const wrapper = mount({ template: "<RouterView />" }, { global: { plugins: [router] }, attachTo: document.body });
  await flushPromises();
  return { wrapper, router };
}

beforeEach(() => {
  setActivePinia(createPinia());
  for (const fn of Object.values(api)) fn.mockReset();
  api.access.mockResolvedValue({
    allowed: true,
    username: "yarden",
    display_name: "Yarden",
    role: "yarden",
    other_member_display_name: "Aviv",
    proposals_waiting_for_you: 1,
  });
  api.summary.mockResolvedValue({
    as_of_date: "2026-12-15",
    buckets: buckets("31166.01"),
    loan_effective_date: "2026-10-01",
    maturity_date: "2027-10-01",
    original_principal_at_start: "30410.00",
    proposals_waiting_for_you: 1,
    proposals_waiting_for_other_member: 0,
  });
  api.proposals.mockResolvedValue([proposal()]);
  api.ledger.mockResolvedValue([]);
  window.confirm = vi.fn(() => true);
});

describe("the Member Loan page", () => {
  it("sends a visitor without a session to sign in and asks the API nothing", async () => {
    const { router } = await mountPage("/member-loan", { status: "anon" as any });
    expect(router.currentRoute.value.name).toBe("login");
    expect(api.access).not.toHaveBeenCalled();
  });

  it("shows the API's refusal to anyone who is not one of the two members", async () => {
    api.access.mockRejectedValue({ response: { status: 403, data: { detail: "member_loan_access_denied" } } });
    const { wrapper } = await mountPage();
    expect(wrapper.find('[data-testid="member-loan.refused"]').text()).toMatch(/only for the two members/);
    expect(wrapper.find('[data-testid="member-loan.tab-today"]').exists()).toBe(false);
  });

  it("shows Amount Owed as the server computed it, for the device's date", async () => {
    const { wrapper } = await mountPage();
    expect(api.summary).toHaveBeenCalledWith(expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/));
    expect(wrapper.find('[data-testid="member-loan.amount-owed"]').text()).toContain("$31,166.01");
    expect(wrapper.find('[data-testid="member-loan.buckets"]').text()).toContain("Accrued interest");
    expect(wrapper.find('[data-testid="member-loan.waiting-count"]').text()).toBe("1");
  });

  it("approves with the fingerprint of the figures shown", async () => {
    api.approve.mockResolvedValue(proposal({ state: "approved" }));
    const { wrapper } = await mountPage("/member-loan?tab=waiting");
    expect(wrapper.find('[data-testid="member-loan.proposal"]').text()).toContain("Withdrawal by Aviv of $1,000.00");
    await wrapper.find('[data-testid="member-loan.approve"]').trigger("click");
    await flushPromises();
    expect(api.approve).toHaveBeenCalledWith("p1", "a".repeat(64));
    expect(wrapper.find('[data-testid="member-loan.notice"]').text()).toMatch(/Approved/);
  });

  it("refreshes the figures when they changed before the approval", async () => {
    api.approve.mockRejectedValue({
      response: { status: 409, data: { detail: { code: "figures_changed", message: "The figures changed since you looked." } } },
    });
    api.proposal.mockResolvedValue(proposal({ figures_changed_since_proposal: true, live_preview: preview("b".repeat(64)) }));
    const { wrapper } = await mountPage("/member-loan?tab=waiting");
    await wrapper.find('[data-testid="member-loan.approve"]').trigger("click");
    await flushPromises();
    expect(wrapper.find('[data-testid="member-loan.error"]').text()).toContain("The figures changed since you looked.");
    expect(wrapper.find('[data-testid="member-loan.figures-changed"]').exists()).toBe(true);
  });

  it("needs a reason to reject", async () => {
    api.reject.mockResolvedValue(proposal({ state: "rejected" }));
    const { wrapper } = await mountPage("/member-loan?tab=waiting");
    await wrapper.find('[data-testid="member-loan.reject-open"]').trigger("click");
    expect(wrapper.find('[data-testid="member-loan.reject"]').attributes("disabled")).toBeDefined();
    await wrapper.find('[data-testid="member-loan.reject-reason"]').setValue("Not what we agreed");
    await wrapper.find('[data-testid="member-loan.reject"]').trigger("submit");
    await flushPromises();
    expect(api.reject).toHaveBeenCalledWith("p1", "Not what we agreed");
  });

  it("warns on a change the signed agreement has no clause for", async () => {
    api.proposals.mockResolvedValue([proposal({ event_type: "yarden_additional_withdrawal_increase", includes_yarden_increase_warning: true })]);
    const { wrapper } = await mountPage("/member-loan?tab=waiting");
    expect(wrapper.find('[data-testid="member-loan.no-clause-warning"]').exists()).toBe(true);
  });

  it("opens the approval card from the e-mail link", async () => {
    const { wrapper } = await mountPage("/member-loan/approvals/p1");
    expect(wrapper.find('[data-testid="member-loan.waiting"]').exists()).toBe(true);
    expect(wrapper.find("#proposal-p1").classes()).toContain("border-primary");
  });

  it("checks the figures, then sends the amount exactly as typed", async () => {
    api.preview.mockResolvedValue(preview());
    api.propose.mockResolvedValue(proposal({ id: "p2", caller_may_approve_or_reject: false, caller_may_cancel: true }));
    const { wrapper } = await mountPage("/member-loan?tab=propose");
    await wrapper.find('[data-testid="member-loan.amount-input"]').setValue("50");
    await wrapper.find('[data-testid="member-loan.date-input"]').setValue("2026-12-15");
    await wrapper.find('[data-testid="member-loan.propose-form"]').trigger("submit");
    await flushPromises();
    expect(api.preview).toHaveBeenCalledWith(expect.objectContaining({ event_type: "lender_withdrawal", amount: "50.00", effective_date: "2026-12-15" }));
    expect(wrapper.find('[data-testid="member-loan.preview"]').text()).toContain("$30,166.01");
    expect(wrapper.find('[data-testid="member-loan.send"]').text()).toContain("Send to Aviv for approval");
    await wrapper.find('[data-testid="member-loan.propose-form"]').trigger("submit");
    await flushPromises();
    expect(api.propose).toHaveBeenCalledWith(expect.objectContaining({ amount: "50.00" }));
  });

  it("asks for the written agreement before an advance or a Yarden withdrawal can be checked", async () => {
    const { wrapper } = await mountPage("/member-loan?tab=propose");
    await wrapper.find('[data-testid="member-loan.type-yarden_additional_withdrawal_increase"]').setValue(true);
    await wrapper.find('[data-testid="member-loan.amount-input"]').setValue("2000");
    expect(wrapper.find('[data-testid="member-loan.written-agreement"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="member-loan.check"]').attributes("disabled")).toBeDefined();
    await wrapper.find("#member-loan-agreement-date").setValue("2026-12-14");
    await wrapper.find("#member-loan-agreement-description").setValue("Side letter");
    expect(wrapper.find('[data-testid="member-loan.check"]').attributes("disabled")).toBeUndefined();
  });

  it("shows the server's plain reason when a preview is refused", async () => {
    api.preview.mockRejectedValue({ response: { data: { detail: { message: "The date cannot be in the future.", code: "date_in_future" } } } });
    const { wrapper } = await mountPage("/member-loan?tab=propose");
    await wrapper.find('[data-testid="member-loan.amount-input"]').setValue("10");
    await wrapper.find('[data-testid="member-loan.propose-form"]').trigger("submit");
    await flushPromises();
    expect(wrapper.find('[data-testid="member-loan.preview-error"]').text()).toBe("The date cannot be in the future.");
    expect(api.propose).not.toHaveBeenCalled();
  });
});

describe("LoanAmountInput", () => {
  it("emits the exact amount text and never reads thousands shorthand", async () => {
    const wrapper = mount(LoanAmountInput, { props: { modelValue: null, id: "amount", label: "Amount" } });
    await wrapper.find("input").setValue("50");
    const emitted = () => wrapper.emitted("update:modelValue")!;
    expect(emitted()[emitted().length - 1]).toEqual(["50.00"]);
    expect(wrapper.find('[data-testid="member-loan.amount-helper"]').text()).toBe("Exactly $50.00");
    await wrapper.find("input").setValue("10.005");
    await wrapper.find("input").trigger("blur");
    expect(emitted()[emitted().length - 1]).toEqual([null]);
    expect(wrapper.find('[data-testid="member-loan.amount-helper"]').text()).toMatch(/at most two decimals/);
  });
});

describe("the session strip", () => {
  async function mountBar(status: "off" | "trusted") {
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: "/", component: { template: "<p/>" } }] });
    await router.push("/");
    useAuthStore().status = status;
    const wrapper = mount(SecurityBar, { global: { plugins: [router] } });
    await flushPromises();
    return wrapper;
  }

  it("links the Member Loan only for a member, with how many changes wait", async () => {
    const wrapper = await mountBar("trusted");
    expect(wrapper.find('[data-testid="security.member-loan-link"]').text()).toContain("Member Loan");
    expect(wrapper.find('[data-testid="security.member-loan-link"]').text()).toContain("1");
  });

  it("asks nothing and shows nothing without a session", async () => {
    const wrapper = await mountBar("off");
    expect(api.access).not.toHaveBeenCalled();
    expect(wrapper.find('[data-testid="security.member-loan-link"]').exists()).toBe(false);
  });

  it("hides the link from a signed-in owner who is not a member", async () => {
    api.access.mockRejectedValue({ response: { status: 403, data: { detail: "member_loan_access_denied" } } });
    const wrapper = await mountBar("trusted");
    expect(wrapper.find('[data-testid="security.member-loan-link"]').exists()).toBe(false);
  });
});
