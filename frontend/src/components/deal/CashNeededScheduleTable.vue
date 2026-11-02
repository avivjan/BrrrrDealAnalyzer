<script setup lang="ts">
/**
 * The dated cash schedule behind Cash Needed, at the lowest ARV — shown under the Cash Needed
 * breakdown in `CalculationBreakdownPopup`, as the HTML report and the PDF show it
 * (`BackEnd/BL/reports/common/cash_needed_schedule_report.py`).
 *
 * One row per cash item in date order (money in reads in the positive colour), the rehab
 * cushion among them: a hold on the purchase closing date, postponed in the liquidity timeline
 * until it is marked done. It computes nothing: the amounts are the engine's, exact to the cent;
 * there is no running balance.
 */
import type { CashNeededScheduleAtLowestArv } from "../../types";
import { formatCalculationStepValueByUnit } from "./calculationStepFormat";

defineProps<{ schedule: CashNeededScheduleAtLowestArv }>();

const SHORT_DATE_FORMAT = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });

function formatScheduleDate(isoDate: string): string {
  return SHORT_DATE_FORMAT.format(new Date(`${isoDate}T00:00:00Z`));
}

function formatScheduleDollars(decimalDollars: string): string {
  return formatCalculationStepValueByUnit("money", Number(decimalDollars));
}

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

  </section>
</template>
