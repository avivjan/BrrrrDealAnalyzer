// @vitest-environment jsdom
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import { startAuthentication } from "@simplewebauthn/browser";

import MemberLoan from "./MemberLoan.vue";
import SecurityBar from "../components/shell/SecurityBar.vue";
import LoanAmountInput from "../components/memberLoan/LoanAmountInput.vue";
import MemberLoanSignaturePad from "../components/memberLoan/MemberLoanSignaturePad.vue";
import { memberLoanApi } from "../api/memberLoan";
import { useAuthStore } from "../stores/authStore";
import type {
  MemberLoanBuckets,
  MemberLoanPreview,
  MemberLoanProposal,
  MemberLoanSigningDocument,
  MemberLoanSigningRequest,
} from "../types/memberLoan";

vi.mock("@simplewebauthn/browser", () => ({
  startAuthentication: vi.fn(),
  startRegistration: vi.fn(),
  browserSupportsWebAuthn: vi.fn(() => true),
}));

vi.mock("../api/memberLoan", () => ({
  memberLoanApi: {
    access: vi.fn(),
    summary: vi.fn(),
    ledger: vi.fn(),
    proposals: vi.fn(),
    proposal: vi.fn(),
    preview: vi.fn(),
    startChangeSigning: vi.fn(),
    startReversalSigning: vi.fn(),
    startDocumentSigning: vi.fn(),
    signingPasskeyOptions: vi.fn(),
    submitSignature: vi.fn(),
    signingRequestPdf: vi.fn(),
    documents: vi.fn(),
    document: vi.fn(),
    documentPdf: vi.fn(),
    signedCopyPdf: vi.fn(),
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
const passkeyPrompt = vi.mocked(startAuthentication);
const DRAWN_SIGNATURE = "data:image/png;base64,iVBORw0KGgo=";

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
    signing_document_id: "d1",
    caller_may_sign_or_reject: true,
    caller_may_cancel: false,
    caller_may_propose_reversal: false,
    includes_yarden_increase_warning: false,
    ...overrides,
  };
}

function signingRequest(overrides: Partial<MemberLoanSigningRequest> = {}): MemberLoanSigningRequest {
  return {
    signing_request_id: "r1",
    signing_purpose: "sign_document",
    document_id: "d1",
    document_sha256: "c".repeat(64),
    document_content: {
      document_kind: "loan_change",
      title: "Loan Change Record No. 1 – Withdrawal by Aviv Jan",
      agreement_reference: "This Change Record is made under the Loan Agreement.",
      change_rows: [["Change", "Withdrawal by Aviv Jan"], ["Amount", "$1,000.00"]],
      contract_basis_lines: ["Section 6.1 of the Agreement: the Lender may withdraw at any time."],
      figures_effective_date: "2026-12-15",
      figures_rows: [["Amount Owed", "$31,166.01", "$30,166.01"]],
      allocation_lines: [],
      effect_lines: ["This record updates the existing loan."],
      warnings: [],
      signers: [],
    },
    signature_meaning: "signed",
    objection_reason: null,
    signature_statement_text: "I, Yarden Kelly, confirm that $1,000.00 was paid. This is a confirmation of fact, not consent.",
    full_legal_name_to_type: "Yarden Kelly",
    electronic_signature_consent_text: "I agree this is my electronic signature.",
    expires_at: "2026-12-15T16:00:00+00:00",
    ...overrides,
  };
}

function statementDocument(overrides: Partial<MemberLoanSigningDocument> = {}): MemberLoanSigningDocument {
  return {
    id: "d2",
    document_kind: "monthly_statement",
    title: "Member Loan statement – November 2026",
    event_id: null,
    statement_month: "2026-11",
    record_number: null,
    created_at: "2026-12-01T11:00:00+00:00",
    document_sha256: "e".repeat(64),
    content: { document_kind: "monthly_statement", title: "Member Loan statement – November 2026", signers: [] },
    signers: [
      { username: "aviv", display_name: "Aviv", legal_name: "Aviv Jan", role_label: "Lender", status: "signed", signed_at: "2026-12-01T12:00:00+00:00", objection_reason: null },
      { username: "yarden", display_name: "Yarden", legal_name: "Yarden Kelly", role_label: "Member, for Big Whales AY LLC", status: "waiting", signed_at: null, objection_reason: null },
    ],
    caller_must_act: true,
    caller_may_object: true,
    proposal_state: null,
    response_deadline: "2026-12-31",
    is_complete: false,
    completed_at: null,
    signed_copy_sha256: null,
    deliveries: [],
    ...overrides,
  };
}

async function walkThroughTheSigningSteps(wrapper: any, typedName = "yarden  KELLY") {
  await wrapper.find('[data-testid="member-loan.signing-next"]').trigger("click");
  await wrapper.find('[data-testid="member-loan.signing-name-input"]').setValue(typedName);
  await wrapper.find('[data-testid="member-loan.signing-next"]').trigger("click");
  wrapper.findComponent(MemberLoanSignaturePad).vm.$emit("change", DRAWN_SIGNATURE);
  await flushPromises();
  await wrapper.find('[data-testid="member-loan.signing-next"]').trigger("click");
  await wrapper.find('[data-testid="member-loan.signing-consent"]').setValue(true);
}

async function mountPage(path = "/member-loan", { status = "trusted" as const } = {}) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/member-loan", name: "member-loan", component: MemberLoan },
      { path: "/member-loan/approvals/:eventId", name: "member-loan-approval", component: MemberLoan, props: true },
      { path: "/member-loan/sign/:documentId", name: "member-loan-sign", component: MemberLoan, props: true },
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
    documents_waiting_for_your_signature: 1,
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
  api.documents.mockResolvedValue([]);
  passkeyPrompt.mockResolvedValue({ id: "cred" } as any);
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

  it("approves by signing: read, type the legal name, draw, consent, then the passkey", async () => {
    api.startDocumentSigning.mockResolvedValue(signingRequest());
    api.signingPasskeyOptions.mockResolvedValue({ passkey_challenge_id: "ch1", options: '{"challenge":"abc"}' });
    api.submitSignature.mockResolvedValue({ document: statementDocument({ id: "d1", document_kind: "loan_change", is_complete: true }), proposal: proposal({ state: "approved" }) });
    const { wrapper } = await mountPage("/member-loan?tab=waiting");
    expect(wrapper.find('[data-testid="member-loan.proposal"]').text()).toContain("Withdrawal by Aviv of $1,000.00");
    await wrapper.find('[data-testid="member-loan.sign-open"]').trigger("click");
    await flushPromises();
    expect(api.startDocumentSigning).toHaveBeenCalledWith("d1", "signed", undefined);
    expect(wrapper.find('[data-testid="member-loan.waiting"]').exists()).toBe(false); // the panel replaces the tab
    expect(wrapper.find('[data-testid="member-loan.signing-statement"]').text()).toContain("confirmation of fact, not consent");
    expect(wrapper.find('[data-testid="member-loan.signing-figures"]').text()).toContain("$30,166.01");

    await walkThroughTheSigningSteps(wrapper);
    await wrapper.find('[data-testid="member-loan.signing-submit"]').trigger("click");
    await flushPromises();
    expect(passkeyPrompt).toHaveBeenCalledWith({ optionsJSON: { challenge: "abc" } });
    expect(api.submitSignature).toHaveBeenCalledWith("r1", {
      typed_full_legal_name: "yarden  KELLY",
      electronic_signature_consent_confirmed: true,
      drawn_signature_png_base64: DRAWN_SIGNATURE,
      passkey_challenge_id: "ch1",
      passkey_credential: { id: "cred" },
    });
    expect(wrapper.find('[data-testid="member-loan.signing"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="member-loan.notice"]').text()).toMatch(/The change is now part of the loan/);
  });

  it("will not go past the name step until it is the member's legal name", async () => {
    api.startDocumentSigning.mockResolvedValue(signingRequest());
    const { wrapper } = await mountPage("/member-loan?tab=waiting");
    await wrapper.find('[data-testid="member-loan.sign-open"]').trigger("click");
    await flushPromises();
    await wrapper.find('[data-testid="member-loan.signing-next"]').trigger("click");
    await wrapper.find('[data-testid="member-loan.signing-name-input"]').setValue("Yarden");
    expect(wrapper.find('[data-testid="member-loan.signing-next"]').attributes("disabled")).toBeDefined();
  });

  it("keeps the panel open with the server's reason when signing is refused", async () => {
    api.startDocumentSigning.mockResolvedValue(signingRequest());
    api.signingPasskeyOptions.mockResolvedValue({ passkey_challenge_id: "ch1", options: "{}" });
    api.submitSignature.mockRejectedValue({ response: { status: 409, data: { detail: { code: "figures_changed", message: "The figures changed." } } } });
    const { wrapper } = await mountPage("/member-loan?tab=waiting");
    await wrapper.find('[data-testid="member-loan.sign-open"]').trigger("click");
    await flushPromises();
    await walkThroughTheSigningSteps(wrapper);
    await wrapper.find('[data-testid="member-loan.signing-submit"]').trigger("click");
    await flushPromises();
    expect(wrapper.find('[data-testid="member-loan.signing-error"]').text()).toBe("The figures changed.");
    await wrapper.find('[data-testid="member-loan.signing-cancel"]').trigger("click");
    expect(wrapper.find('[data-testid="member-loan.waiting"]').exists()).toBe(true);
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

  it("explains a Yarden withdrawal increases the loan under Section 7A", async () => {
    api.proposals.mockResolvedValue([proposal({ event_type: "yarden_additional_withdrawal_increase", includes_yarden_increase_warning: true })]);
    const { wrapper } = await mountPage("/member-loan?tab=waiting");
    expect(wrapper.find('[data-testid="member-loan.no-clause-warning"]').exists()).toBe(true);
  });

  it("opens the statement to sign or object from the e-mail's sign link", async () => {
    api.document.mockResolvedValue(statementDocument());
    api.documents.mockResolvedValue([statementDocument()]);
    api.statement.mockResolvedValue({
      statement_month: "2026-11",
      document: {
        title: "Member Loan statement – November 2026", statement_month: "2026-11", statement_date: "2026-12-01", summary_rows: [],
        what_happened_sentences: [], interest_period_lines: [], interest_total_lines: [], debt_equation_lines: [], amount_owed_lines: [],
        how_it_works_lines: [], warnings: [], binding_sentence: "Binding.", engine_version: "1", ledger_fingerprint: "f",
      },
      is_final: true, sent_at: "2026-12-01T11:00:00+00:00", objection_deadline: "2026-12-31", sent_to: [], signing_document_id: "d2",
    });
    api.startDocumentSigning.mockResolvedValue(signingRequest({ signature_meaning: "objected", objection_reason: "Too high" }));
    const { wrapper } = await mountPage("/member-loan/sign/d2");
    expect(api.statement).toHaveBeenCalledWith("2026-11");
    const signers = wrapper.findAll('[data-testid="member-loan.statement-signer"]');
    expect(signers.map((s) => s.attributes("data-status"))).toEqual(["signed", "waiting"]);
    await wrapper.find('[data-testid="member-loan.statement-object-open"]').trigger("click");
    expect(wrapper.find('[data-testid="member-loan.statement-object"]').attributes("disabled")).toBeDefined();
    await wrapper.find('[data-testid="member-loan.statement-objection-reason"]').setValue("Too high");
    await wrapper.find('[data-testid="member-loan.statement-object"]').trigger("submit");
    await flushPromises();
    expect(api.startDocumentSigning).toHaveBeenCalledWith("d2", "objected", "Too high");
    expect(wrapper.find('[data-testid="member-loan.signing-submit"]').exists()).toBe(false); // the reading step comes first
    expect(wrapper.find('[data-testid="member-loan.signing"]').text()).toContain("Signing an objection");
  });

  it("opens the approval card from the e-mail link", async () => {
    const { wrapper } = await mountPage("/member-loan/approvals/p1");
    expect(wrapper.find('[data-testid="member-loan.waiting"]').exists()).toBe(true);
    expect(wrapper.find("#proposal-p1").classes()).toContain("border-primary");
  });

  it("checks the figures, then sends the amount exactly as typed", async () => {
    api.preview.mockResolvedValue(preview());
    api.startChangeSigning.mockResolvedValue(signingRequest({ signing_purpose: "propose_change", document_id: null }));
    const { wrapper } = await mountPage("/member-loan?tab=propose");
    await wrapper.find('[data-testid="member-loan.amount-input"]').setValue("50");
    await wrapper.find('[data-testid="member-loan.date-input"]').setValue("2026-12-15");
    await wrapper.find('[data-testid="member-loan.propose-form"]').trigger("submit");
    await flushPromises();
    expect(api.preview).toHaveBeenCalledWith(expect.objectContaining({ event_type: "lender_withdrawal", amount: "50.00", effective_date: "2026-12-15" }));
    expect(wrapper.find('[data-testid="member-loan.preview"]').text()).toContain("$30,166.01");
    expect(wrapper.find('[data-testid="member-loan.send"]').text()).toContain("Review and sign");
    await wrapper.find('[data-testid="member-loan.propose-form"]').trigger("submit");
    await flushPromises();
    expect(api.startChangeSigning).toHaveBeenCalledWith(expect.objectContaining({ amount: "50.00" }));
    expect(wrapper.find('[data-testid="member-loan.signing"]').attributes("data-purpose")).toBe("propose_change");
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
    expect(api.startChangeSigning).not.toHaveBeenCalled();
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
