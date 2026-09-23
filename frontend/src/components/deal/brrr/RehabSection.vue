<script setup lang="ts">
/**
 * BRRRR › Rehab: what the work costs, what the lender finances, and the spread between.
 *
 * Mirror-once: both amounts start at 0; the first value typed into either seeds the
 * other, after which they are independent (a real budget rarely equals the actual).
 * Only while BOTH are still empty, so opening a saved cash-rehab deal never turns it
 * into a financed one.
 *
 * The seed is asymmetric on purpose. Typing the actual rehab first seeds the budget at
 * rehab × (1 + contingency) — the amount the lender should finance so the contingency is
 * drawn, not paid from pocket (110% at the default 10%). Typing the budget first copies
 * it to the rehab unchanged: a budget is the lender's number, and deriving a rehab from
 * it would only invent a figure.
 */
import { computed, ref } from "vue";
import type { DealInputModel } from "../../../types";
import { useDealField } from "../../../composables/useDealField";
import { brrrAutoCalc } from "../../../utils/brrrAutoCalc";
import { impactText } from "../../../config/brrrInputImpacts";
import { formatMoney } from "../../../utils/money";
import MoneyInput from "../../ui/MoneyInput.vue";
import NumberInput from "../../ui/NumberInput.vue";
import LifecycleSection from "../LifecycleSection.vue";
import AutoFigure from "../AutoFigure.vue";

const props = defineProps<{ deal: DealInputModel; surface: "card" | "panel" }>();
const field = useDealField(props.deal);
const autoCalc = computed(() => brrrAutoCalc(props.deal));

const mirroredOnce = ref(false);
const isEmptyAmount = (amount: number | null) => !amount;

/** Thousands at NUMERIC(14,4): 50 × 1.1 is 55.000000000000007 in floating point, so round. */
const roundToFourDecimals = (amount: number) => Math.round(amount * 10_000) / 10_000;

const constructionBudgetSeededFromRehab = (rehabCostThousands: number) =>
  roundToFourDecimals(rehabCostThousands * (1 + (field.get("rehabContingency") ?? 0) / 100));

const setActualRehabCost = (newRehabCostThousands: number | null) => {
  const bothAmountsEmpty = isEmptyAmount(field.get("rehabCost")) && isEmptyAmount(field.get("constructionLoanBudget"));
  field.set("rehabCost", newRehabCostThousands);
  if (!mirroredOnce.value && bothAmountsEmpty && newRehabCostThousands != null) {
    field.set("constructionLoanBudget", constructionBudgetSeededFromRehab(newRehabCostThousands));
  }
  mirroredOnce.value = true;
};
const setConstructionLoanBudget = (newBudgetThousands: number | null) => {
  const bothAmountsEmpty = isEmptyAmount(field.get("rehabCost")) && isEmptyAmount(field.get("constructionLoanBudget"));
  field.set("constructionLoanBudget", newBudgetThousands);
  if (!mirroredOnce.value && bothAmountsEmpty && newBudgetThousands != null) field.set("rehabCost", newBudgetThousands);
  mirroredOnce.value = true;
};

const stolenLabel = computed(() =>
  autoCalc.value.stolenMoney != null && autoCalc.value.stolenMoney < 0 ? "Extra out of pocket (rehab beyond budget)" : "Stolen Money (draw spread)",
);
</script>

<template>
  <LifecycleSection title="Rehab" icon="pi-wrench" :surface="surface">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <MoneyInput
        data-testid="form.field.rehabCost"
        :model-value="field.get('rehabCost')"
        @update:model-value="setActualRehabCost"
        label="Actual Rehab Cost"
        :inThousands="true"
        :needed-to-run-analysis="true"
        :info="impactText('rehabCost')"
      />
      <MoneyInput
        data-testid="form.field.constructionLoanBudget"
        :model-value="field.get('constructionLoanBudget')"
        @update:model-value="setConstructionLoanBudget"
        label="Construction Loan Budget"
        :inThousands="true"
        placeholder="rehab + contingency"
        :info="impactText('constructionLoanBudget')"
        :note="autoCalc.hmlAmount == null ? undefined : `HML total ${formatMoney(autoCalc.hmlAmount)}`"
      />
      <NumberInput
        data-testid="form.field.rehabContingency"
        :model-value="field.get('rehabContingency')"
        @update:model-value="(v: number | null) => field.set('rehabContingency', v)"
        label="Contingency"
        suffix="%"
        :min="0"
        :max="100"
        :info="impactText('rehabContingency')"
        :note="autoCalc.rehabCostWithContingency == null ? undefined : `rehab ${formatMoney(autoCalc.rehabCostWithContingency)}`"
      />
      <MoneyInput
        data-testid="form.field.rehabCushion"
        :model-value="field.get('rehabCushion')"
        @update:model-value="(v: number | null) => field.set('rehabCushion', v)"
        label="Rehab Cushion"
        :info="impactText('rehabCushion')"
      />
    </div>
    <template #footer>
      <AutoFigure data-testid="form.auto.stolenMoney" :label="stolenLabel" :value="autoCalc.stolenMoney" hint="construction budget − actual rehab (with contingency)" signed />
    </template>
  </LifecycleSection>
</template>
