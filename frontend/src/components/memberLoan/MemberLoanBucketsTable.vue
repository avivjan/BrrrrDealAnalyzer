<script setup lang="ts">
/** The loan's buckets, alone or as before → after. Figures are the server's text. */
import { computed } from "vue";

import type { MemberLoanBuckets } from "../../types/memberLoan";
import { BUCKET_LABELS, formatLoanMoney } from "../../utils/memberLoanText";

const props = defineProps<{ after: MemberLoanBuckets; before?: MemberLoanBuckets | null; lenderName?: string; showCapitalCredited?: boolean }>();

type BucketKey = keyof MemberLoanBuckets;
const ORDER: BucketKey[] = ["original_principal", "capitalized_interest", "total_balance", "accrued_interest", "interest_payable", "amount_owed"];

const rows = computed(() => {
  const interestPayableIsInUse = props.after.interest_payable !== "0.00" || (props.before?.interest_payable ?? "0.00") !== "0.00";
  const keys = ORDER.filter((key) => key !== "interest_payable" || interestPayableIsInUse);
  if (props.showCapitalCredited) keys.push("lender_capital_credited");
  return keys.map((key) => ({
    key,
    label: key === "lender_capital_credited" && props.lenderName ? `Credited to ${props.lenderName}'s capital account` : BUCKET_LABELS[key],
    before: props.before ? formatLoanMoney(props.before[key]) : null,
    after: formatLoanMoney(props.after[key]),
    changed: props.before ? props.before[key] !== props.after[key] : false,
    emphasised: key === "total_balance" || key === "amount_owed",
  }));
});
</script>

<template>
  <table class="w-full text-sm" data-testid="member-loan.buckets">
    <thead v-if="before">
      <tr class="text-xs text-fg-muted">
        <th class="py-1 text-left font-normal"><span class="sr-only">Bucket</span></th>
        <th class="py-1 text-right font-normal">Before</th>
        <th class="py-1 text-right font-normal">After</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="row in rows" :key="row.key" class="border-t border-line/60" :data-bucket="row.key">
        <th scope="row" class="py-1.5 pr-3 text-left font-normal" :class="row.emphasised ? 'font-semibold text-fg' : 'text-fg-muted'">{{ row.label }}</th>
        <td v-if="before" class="py-1.5 pl-3 text-right tabular-nums text-fg-muted">{{ row.before }}</td>
        <td class="py-1.5 pl-3 text-right tabular-nums" :class="[row.emphasised ? 'font-semibold text-fg' : 'text-fg', row.changed && 'text-primary']">{{ row.after }}</td>
      </tr>
    </tbody>
  </table>
</template>
