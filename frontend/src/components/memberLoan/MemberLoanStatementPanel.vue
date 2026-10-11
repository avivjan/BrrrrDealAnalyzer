<script setup lang="ts">
/** One month's statement, in the same six sections as the PDF. */
import type { MemberLoanStatement } from "../../types/memberLoan";
import { formatLoanDate } from "../../utils/memberLoanText";

defineProps<{ statement: MemberLoanStatement }>();
</script>

<template>
  <div class="flex flex-col gap-5" data-testid="member-loan.statement">
    <div>
      <h3 class="text-lg font-semibold text-fg">{{ statement.document.title }}</h3>
      <p class="text-sm text-fg-muted" data-testid="member-loan.statement-status">
        <template v-if="statement.is_final">
          Final. Sent on {{ formatLoanDate(statement.sent_at) }} to {{ statement.sent_to.join(", ") }}. Objections in writing by
          {{ formatLoanDate(statement.objection_deadline) }}.
        </template>
        <template v-else>Not final yet.</template>
      </p>
    </div>

    <section aria-labelledby="statement-summary">
      <h4 id="statement-summary" class="mb-2 text-sm font-semibold text-fg">1. Summary</h4>
      <dl class="grid gap-x-6 gap-y-1 rounded-ctl border border-line bg-surface-muted p-3 text-sm sm:grid-cols-2">
        <template v-for="[label, value] in statement.document.summary_rows" :key="label">
          <dt class="text-fg-muted">{{ label }}</dt>
          <dd class="text-right font-semibold tabular-nums text-fg sm:text-left">{{ value }}</dd>
        </template>
      </dl>
    </section>

    <section aria-labelledby="statement-events">
      <h4 id="statement-events" class="mb-2 text-sm font-semibold text-fg">2. What happened this month</h4>
      <ul class="flex flex-col gap-2 text-sm text-fg">
        <li v-for="sentence in statement.document.what_happened_sentences" :key="sentence">{{ sentence }}</li>
      </ul>
    </section>

    <section aria-labelledby="statement-interest">
      <h4 id="statement-interest" class="mb-2 text-sm font-semibold text-fg">3. How the interest was calculated</h4>
      <p class="mb-1 text-xs text-fg-muted">Each stretch of days: balance × rate × days/30.</p>
      <ul class="flex flex-col gap-1 text-sm tabular-nums text-fg">
        <li v-for="line in statement.document.interest_period_lines" :key="line">{{ line }}</li>
        <li v-for="(line, index) in statement.document.interest_total_lines" :key="line" :class="index === statement.document.interest_total_lines.length - 1 && 'font-semibold'">
          {{ line }}
        </li>
      </ul>
    </section>

    <section aria-labelledby="statement-debt">
      <h4 id="statement-debt" class="mb-2 text-sm font-semibold text-fg">4. How the total debt was calculated</h4>
      <ul class="flex flex-col gap-1 text-sm tabular-nums text-fg">
        <li v-for="line in statement.document.debt_equation_lines" :key="line" :class="line.startsWith('=') && 'font-semibold'">{{ line }}</li>
        <li v-for="(line, index) in statement.document.amount_owed_lines" :key="line" :class="index === 0 && 'pt-2 font-semibold'">{{ line }}</li>
      </ul>
    </section>

    <section aria-labelledby="statement-how" class="rounded-ctl border border-line bg-surface-muted p-3">
      <h4 id="statement-how" class="mb-2 text-sm font-semibold text-fg">5. How the calculation works</h4>
      <ul class="list-disc space-y-1 pl-5 text-sm text-fg">
        <li v-for="line in statement.document.how_it_works_lines" :key="line">{{ line }}</li>
      </ul>
    </section>

    <section aria-labelledby="statement-notes">
      <h4 id="statement-notes" class="mb-2 text-sm font-semibold text-fg">6. Notes</h4>
      <p
        v-for="warning in statement.document.warnings"
        :key="warning"
        class="mb-2 rounded-ctl border border-warning/50 bg-warning/10 p-2 text-sm font-medium text-fg"
        data-testid="member-loan.statement-warning"
      >
        {{ warning }}
      </p>
      <p class="text-sm font-semibold text-fg">{{ statement.document.binding_sentence }}</p>
      <p class="mt-1 break-all text-xs text-fg-muted">
        Engine version {{ statement.document.engine_version }}. Ledger fingerprint: {{ statement.document.ledger_fingerprint }}
      </p>
    </section>
  </div>
</template>
