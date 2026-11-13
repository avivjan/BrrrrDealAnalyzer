<script setup lang="ts">
/**
 * The dated cash schedule behind Cash Needed, at the lowest ARV — shown under the Cash Needed
 * breakdown in `CalculationBreakdownPopup`, as the HTML report and the PDF show it
 * (`BackEnd/BL/reports/common/cash_needed_schedule_report.py`).
 *
 * One row per cash item in date order (money in reads in the positive colour), the construction
 * account's two rows among them: the deposit into it on the purchase closing date (the rehab
 * cushion, plus any rehab beyond the budget) and what it gives back on the rehab completion.
 * It computes nothing: the amounts are the engine's, exact to the cent;
 * there is no running balance.
 *
 * The deal's key dates (contract signed, purchase closing, rehab completed, tenant moves in, the
 * Nov 30 tax bill inside the hold, refi closing) sit among the rows so the schedule reads as a
 * timeline: tinted, uppercase markers with a flag and no amount, each listed first on its day.
 * They are markers, not cash.
 */
import { computed } from "vue";
import type { CashNeededScheduleAtLowestArv, CashNeededScheduleMilestone, CashNeededScheduleRow } from "../../types";
import { formatCalculationStepValueByUnit } from "./calculationStepFormat";

const props = defineProps<{ schedule: CashNeededScheduleAtLowestArv }>();

type ScheduleLine =
  | { kind: "milestone"; date: string; milestone: CashNeededScheduleMilestone }
  | { kind: "cashRow"; date: string; cashRow: CashNeededScheduleRow };

/** The cash rows and the key dates merged by date, a key date first on its day (each list keeps its own order). */
const scheduleLinesInDateOrder = computed<ScheduleLine[]>(() => {
  const milestoneLines: ScheduleLine[] = (props.schedule.deal_milestones ?? []).map((milestone) => ({ kind: "milestone", date: milestone.date, milestone }));
  const cashRowLines: ScheduleLine[] = props.schedule.dated_cash_rows.map((cashRow) => ({ kind: "cashRow", date: cashRow.date, cashRow }));
  const kindOrderWithinDay = (line: ScheduleLine) => (line.kind === "milestone" ? 0 : 1);
  return [...milestoneLines, ...cashRowLines].sort(
    (first, second) => first.date.localeCompare(second.date) || kindOrderWithinDay(first) - kindOrderWithinDay(second),
  );
});

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
          <template v-for="line in scheduleLinesInDateOrder" :key="line.kind === 'milestone' ? `milestone-${line.milestone.milestone_key}` : `${line.cashRow.date}-${line.cashRow.sequence_within_day}`">
            <tr
              v-if="line.kind === 'milestone'"
              data-part="schedule-milestone"
              :data-milestone-key="line.milestone.milestone_key"
              class="border-t border-line bg-primary/10 text-primary"
            >
              <td class="whitespace-nowrap border-l-2 border-primary px-3 py-1 text-[11px] font-semibold uppercase tracking-wider tabular">{{ formatScheduleDate(line.milestone.date) }}</td>
              <td colspan="2" class="px-3 py-1 text-[11px] font-semibold uppercase tracking-wider">
                <i class="pi pi-flag mr-1.5 text-[10px]" aria-hidden="true"></i>{{ line.milestone.description }}
              </td>
            </tr>
            <tr
              v-else
              data-part="schedule-row"
              :data-item-key="line.cashRow.item_key"
              class="border-t border-line align-top"
            >
              <td class="whitespace-nowrap px-3 py-1.5 text-fg-muted tabular">{{ formatScheduleDate(line.cashRow.date) }}</td>
              <td class="px-3 py-1.5 text-fg">{{ line.cashRow.description }}</td>
              <td
                class="numeric tabular whitespace-nowrap px-3 py-1.5 text-right"
                :class="Number(line.cashRow.signed_amount_dollars) > 0 ? 'text-positive' : 'text-fg'"
              >
                {{ formatScheduleDollars(line.cashRow.signed_amount_dollars) }}
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

  </section>
</template>
