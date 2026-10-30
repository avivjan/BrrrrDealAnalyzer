<script setup lang="ts">
/**
 * The dated cash schedule behind Cash Needed, at the lowest ARV — shown under the Cash Needed
 * breakdown in `CalculationBreakdownPopup`, as the HTML report and the PDF show it
 * (`BackEnd/BL/reports/common/cash_needed_schedule_report.py`).
 *
 * Three blocks: one row per cash item in date order (money in reads in the positive colour),
 * the money that must stay in the account (the rehab cushion and its window), and the summary
 * "dated rows total + cushion = Total Cash Needed". It computes nothing: the amounts are the
 * engine's, exact to the cent; there is no running balance.
 */
import { computed } from "vue";

import type { CashNeededScheduleAtLowestArv } from "../../types";
import { formatCalculationStepValueByUnit } from "./calculationStepFormat";

const props = defineProps<{ schedule: CashNeededScheduleAtLowestArv }>();

const SHORT_DATE_FORMAT = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });

function formatScheduleDate(isoDate: string): string {
  return SHORT_DATE_FORMAT.format(new Date(`${isoDate}T00:00:00Z`));
}

function formatScheduleDollars(decimalDollars: string): string {
  return formatCalculationStepValueByUnit("money", Number(decimalDollars));
}

const summaryLines = computed(() => [
  { key: "dated", label: "Dated rows total (net out)", value: formatScheduleDollars(props.schedule.dated_cash_rows_net_outflow_dollars) },
  { key: "held", label: "+ Rehab cushion (must stay in the account)", value: formatScheduleDollars(props.schedule.cash_that_must_stay_in_account_total_dollars) },
  { key: "total", label: "= Total Cash Needed", value: formatScheduleDollars(props.schedule.total_cash_needed_dollars) },
]);
</script>

<template>
  <section data-testid="cash-needed-schedule" class="mt-4" aria-label="Cash schedule (Lowest ARV)">
    <p class="mb-1 text-xs font-semibold uppercase tracking-wider text-fg-muted">Cash schedule (Lowest ARV)</p>
    <div class="overflow-x-auto rounded-card border border-line bg-surface-2">
      <table class="w-full border-collapse text-sm">
        <thead>
          <tr class="text-left text-xs uppercase tracking-wider text-fg-muted">
            <th class="px-3 py-2 font-semibold">Date</th>
            <th class="px-3 py-2 font-semibold">Item</th>
            <th class="px-3 py-2 text-right font-semibold">Amount</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in schedule.dated_cash_rows"
            :key="`${row.date}-${row.sequence_within_day}`"
            data-part="schedule-row"
            :data-item-key="row.item_key"
            class="border-t border-line align-top"
          >
            <td class="whitespace-nowrap px-3 py-1.5 text-fg-muted tabular">{{ formatScheduleDate(row.date) }}</td>
            <td class="px-3 py-1.5 text-fg">{{ row.description }}</td>
            <td
              class="numeric tabular whitespace-nowrap px-3 py-1.5 text-right"
              :class="Number(row.signed_amount_dollars) > 0 ? 'text-positive' : 'text-fg'"
            >
              {{ formatScheduleDollars(row.signed_amount_dollars) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="mb-1 mt-4 text-xs font-semibold uppercase tracking-wider text-fg-muted">Must stay in the account (not spent)</p>
    <ul class="m-0 list-none space-y-2 p-0">
      <li
        v-for="held in schedule.cash_that_must_stay_in_account"
        :key="held.item_key"
        data-part="must-stay-in-account"
        class="rounded-card border border-line bg-surface-2 px-3 py-2 text-sm"
      >
        <div class="flex items-baseline justify-between gap-3">
          <span class="text-fg">{{ held.description }}</span>
          <span class="numeric tabular font-semibold text-fg">{{ formatScheduleDollars(held.amount_dollars) }}</span>
        </div>
        <p class="mt-0.5 text-xs text-fg-muted">
          {{ formatScheduleDate(held.reserve_starts_on_date) }} → {{ formatScheduleDate(held.reserve_ends_on_date) }}
        </p>
      </li>
      <li v-if="!schedule.cash_that_must_stay_in_account.length" class="text-sm text-fg-muted">Nothing</li>
    </ul>

    <dl data-part="schedule-summary" class="mt-3 space-y-1 text-sm">
      <div
        v-for="line in summaryLines"
        :key="line.key"
        class="flex items-baseline justify-between gap-3"
        :class="line.key === 'total' ? 'border-t border-line pt-1 font-bold' : ''"
      >
        <dt class="text-fg">{{ line.label }}</dt>
        <dd class="numeric tabular m-0 text-fg">{{ line.value }}</dd>
      </div>
    </dl>
  </section>
</template>
