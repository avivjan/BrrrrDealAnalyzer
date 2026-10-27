<script setup lang="ts">
/**
 * Signing one document, the way Amendment No. 1, Section 1.2 describes it:
 *   1. Read     the document (what the PDF says, on screen) and open the PDF;
 *   2. Name     type your full legal name;
 *   3. Draw     your signature;
 *   4. Confirm  tick the consent, then sign with your passkey.
 * The passkey's challenge is bound to this document's SHA-256 by the server,
 * so the signature covers exactly what was shown. The store does the calls.
 */
import { computed, ref } from "vue";

import { useMemberLoanStore } from "../../stores/memberLoanStore";
import type { MemberLoanSigningRequest } from "../../types/memberLoan";
import { formatLoanDate } from "../../utils/memberLoanText";
import MemberLoanSignaturePad from "./MemberLoanSignaturePad.vue";

const props = defineProps<{ signingRequest: MemberLoanSigningRequest }>();
const emit = defineEmits<{ signed: [] }>();

const loan = useMemberLoanStore();

type StepKey = "read" | "name" | "draw" | "confirm";
const STEPS: { key: StepKey; label: string }[] = [
  { key: "read", label: "Read" },
  { key: "name", label: "Type your name" },
  { key: "draw", label: "Draw your signature" },
  { key: "confirm", label: "Confirm and sign" },
];

const step = ref<StepKey>("read");
const typedFullLegalName = ref("");
const drawnSignaturePng = ref<string | null>(null);
const consentConfirmed = ref(false);

const content = computed(() => props.signingRequest.document_content);
const isStatement = computed(() => content.value.document_kind === "monthly_statement");
const isObjection = computed(() => props.signingRequest.signature_meaning === "objected");
const stepIndex = computed(() => STEPS.findIndex((s) => s.key === step.value));
const nameMatches = computed(
  () => normalized(typedFullLegalName.value) === normalized(props.signingRequest.full_legal_name_to_type),
);
const signing = computed(() => loan.busyKey === "signing");

function normalized(name: string): string {
  return name.split(/\s+/).filter(Boolean).join(" ").toLowerCase();
}

function stepState(index: number): "done" | "active" | "todo" {
  if (index < stepIndex.value) return "done";
  return index === stepIndex.value ? "active" : "todo";
}

function go(next: StepKey) {
  step.value = next;
}

async function sign() {
  if (!drawnSignaturePng.value || !consentConfirmed.value || !nameMatches.value) return;
  const completion = await loan.completeSigning({
    typedFullLegalName: typedFullLegalName.value,
    electronicSignatureConsentConfirmed: consentConfirmed.value,
    drawnSignaturePngBase64: drawnSignaturePng.value,
  });
  if (completion) emit("signed");
}
</script>

<template>
  <UiCard padding="md" class="flex flex-col gap-4" data-testid="member-loan.signing" :data-purpose="signingRequest.signing_purpose">
    <div class="flex flex-wrap items-start justify-between gap-2">
      <div class="min-w-0">
        <p class="text-xs uppercase tracking-wide text-fg-muted">{{ isObjection ? "Signing an objection" : "Signing" }}</p>
        <h2 class="text-lg font-semibold text-fg" data-testid="member-loan.signing-title">{{ content.title }}</h2>
      </div>
      <UiButton variant="ghost" size="sm" :disabled="signing" data-testid="member-loan.signing-cancel" @click="loan.cancelSigning()">
        Cancel
      </UiButton>
    </div>

    <UiStepper :count="STEPS.length" compact>
      <li v-for="(item, index) in STEPS" :key="item.key" :data-step="stepState(index)" :title="item.label">{{ index + 1 }}. {{ item.label }}</li>
    </UiStepper>

    <!-- 1. Read -->
    <div v-if="step === 'read'" class="flex flex-col gap-4" data-testid="member-loan.signing-read">
      <template v-if="!isStatement">
        <p class="text-sm text-fg-muted">{{ content.agreement_reference }}</p>
        <section>
          <h3 class="mb-1 text-sm font-semibold text-fg">What changes</h3>
          <dl class="grid grid-cols-[minmax(0,10rem)_1fr] gap-x-3 gap-y-1 text-sm">
            <template v-for="[label, value] in content.change_rows" :key="label">
              <dt class="text-fg-muted">{{ label }}</dt>
              <dd class="text-fg">{{ value }}</dd>
            </template>
          </dl>
        </section>
        <section>
          <h3 class="mb-1 text-sm font-semibold text-fg">What the Agreement says</h3>
          <ul class="list-disc space-y-1 pl-5 text-sm text-fg">
            <li v-for="line in content.contract_basis_lines" :key="line">{{ line }}</li>
          </ul>
        </section>
        <section>
          <h3 class="mb-1 text-sm font-semibold text-fg">Figures before and after, on {{ formatLoanDate(content.figures_effective_date) }}</h3>
          <div class="overflow-x-auto rounded-ctl border border-line" tabindex="0" role="region" aria-label="Figures before and after">
            <table class="w-full min-w-[22rem] text-sm" data-testid="member-loan.signing-figures">
              <thead class="bg-surface-muted text-xs text-fg-muted">
                <tr><th class="px-3 py-2 text-left font-medium">Figure</th><th class="px-3 py-2 text-right font-medium">Before</th><th class="px-3 py-2 text-right font-medium">After</th></tr>
              </thead>
              <tbody>
                <tr v-for="[label, before, after] in content.figures_rows" :key="label" class="border-t border-line/60" :class="label === 'Amount Owed' ? 'font-semibold' : ''">
                  <td class="px-3 py-2">{{ label }}</td>
                  <td class="px-3 py-2 text-right tabular-nums">{{ before }}</td>
                  <td class="px-3 py-2 text-right tabular-nums">{{ after }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-for="line in content.allocation_lines" :key="line" class="mt-2 text-sm text-fg-muted">{{ line }}</p>
          <p v-for="warning in content.warnings" :key="warning" class="mt-2 rounded-ctl border border-warning/40 bg-warning/10 p-2 text-sm text-fg">{{ warning }}</p>
        </section>
        <ul class="list-disc space-y-1 pl-5 text-sm text-fg">
          <li v-for="line in content.effect_lines" :key="line">{{ line }}</li>
        </ul>
      </template>
      <template v-else>
        <p class="text-sm text-fg">
          Amount Owed on {{ formatLoanDate(content.statement_date) }}: <strong data-testid="member-loan.signing-amount-owed">{{ content.amount_owed }}</strong>
        </p>
        <ul class="list-disc space-y-1 pl-5 text-sm text-fg">
          <li v-for="sentence in content.statement_document?.what_happened_sentences ?? []" :key="sentence">{{ sentence }}</li>
        </ul>
        <p v-for="line in content.acknowledgment_intro_lines" :key="line" class="text-sm text-fg-muted">{{ line }}</p>
      </template>

      <section class="rounded-ctl border-l-4 border-primary bg-surface-muted p-3">
        <h3 class="mb-1 text-sm font-semibold text-fg">What your signature says</h3>
        <p class="whitespace-pre-line text-sm text-fg" data-testid="member-loan.signing-statement">{{ signingRequest.signature_statement_text }}</p>
      </section>

      <div class="flex flex-wrap items-center justify-between gap-2">
        <UiButton variant="secondary" size="sm" :loading="loan.busyKey === 'signing-pdf'" data-testid="member-loan.signing-pdf" @click="loan.downloadSigningRequestPdf()">
          <i class="pi pi-file-pdf" aria-hidden="true" /> Open the full PDF
        </UiButton>
        <UiButton size="sm" data-testid="member-loan.signing-next" @click="go('name')">I have read it: continue</UiButton>
      </div>
      <p class="text-xs text-fg-muted">The PDF is the document you sign. Its fingerprint (SHA-256): <span class="break-all font-mono">{{ signingRequest.document_sha256 }}</span></p>
    </div>

    <!-- 2. Name -->
    <div v-if="step === 'name'" class="flex flex-col gap-3" data-testid="member-loan.signing-name">
      <label for="member-loan-legal-name" class="text-sm font-medium text-fg">Type your full legal name: {{ signingRequest.full_legal_name_to_type }}</label>
      <input
        id="member-loan-legal-name"
        v-model="typedFullLegalName"
        type="text"
        autocomplete="name"
        class="rounded-ctl border border-line bg-page px-3 py-2 text-base text-fg"
        data-testid="member-loan.signing-name-input"
      />
      <p v-if="typedFullLegalName && !nameMatches" class="text-xs text-negative">It must be exactly your name as in the Agreement.</p>
      <div class="flex justify-between gap-2">
        <UiButton variant="ghost" size="sm" @click="go('read')">Back</UiButton>
        <UiButton size="sm" :disabled="!nameMatches" data-testid="member-loan.signing-next" @click="go('draw')">Continue</UiButton>
      </div>
    </div>

    <!-- 3. Draw -->
    <div v-if="step === 'draw'" class="flex flex-col gap-3" data-testid="member-loan.signing-draw">
      <p class="text-sm font-medium text-fg">Draw your signature</p>
      <MemberLoanSignaturePad @change="(png) => (drawnSignaturePng = png)" />
      <div class="flex justify-between gap-2">
        <UiButton variant="ghost" size="sm" @click="go('name')">Back</UiButton>
        <UiButton size="sm" :disabled="!drawnSignaturePng" data-testid="member-loan.signing-next" @click="go('confirm')">Continue</UiButton>
      </div>
    </div>

    <!-- 4. Confirm -->
    <div v-if="step === 'confirm'" class="flex flex-col gap-3" data-testid="member-loan.signing-confirm">
      <div class="flex flex-wrap items-center gap-4 rounded-ctl border border-line bg-page p-3">
        <img v-if="drawnSignaturePng" :src="drawnSignaturePng" alt="Your drawn signature" class="h-16 w-48 object-contain" />
        <div class="text-sm">
          <p class="font-semibold text-fg">{{ typedFullLegalName.trim() }}</p>
          <p class="text-fg-muted">{{ isObjection ? `Objecting: ${signingRequest.objection_reason}` : content.title }}</p>
        </div>
      </div>
      <label class="flex items-start gap-2 text-sm text-fg">
        <input v-model="consentConfirmed" type="checkbox" class="mt-1 h-4 w-4" data-testid="member-loan.signing-consent" />
        <span>{{ signingRequest.electronic_signature_consent_text }}</span>
      </label>
      <p v-if="loan.signingErrorMessage" class="rounded-ctl border border-negative/40 bg-negative/10 p-3 text-sm text-fg" role="alert" data-testid="member-loan.signing-error">
        {{ loan.signingErrorMessage }}
      </p>
      <div class="flex justify-between gap-2">
        <UiButton variant="ghost" size="sm" :disabled="signing" @click="go('draw')">Back</UiButton>
        <UiButton :disabled="!consentConfirmed || !drawnSignaturePng || !nameMatches" :loading="signing" data-testid="member-loan.signing-submit" @click="sign">
          <i class="pi pi-key" aria-hidden="true" /> {{ isObjection ? "Sign the objection with my passkey" : "Sign with my passkey" }}
        </UiButton>
      </div>
      <p class="text-xs text-fg-muted">Your passkey confirms it is you. A copy of the signed document is e-mailed to both members and the company once everyone has signed.</p>
    </div>
  </UiCard>
</template>
