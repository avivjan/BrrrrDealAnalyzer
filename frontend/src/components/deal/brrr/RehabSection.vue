<script setup lang="ts">
/**
 * BRRRR › Rehab: what the work costs, what the lender finances, and the spread between.
 *
 * Mirror-once: both amounts start at 0; the first value typed into either is copied to
 * the other, after which they are independent (a real budget rarely equals the actual).
 * Only while BOTH are still empty, so opening a saved cash-rehab deal never turns it
 * into a financed one.
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
const f = useDealField(props.deal);
const calc = computed(() => brrrAutoCalc(props.deal));

const mirrored = ref(false);
const empty = (v: number | null) => !v;

const setRehab = (v: number | null) => {
  const bothEmpty = empty(f.get("rehabCost")) && empty(f.get("constructionLoanBudget"));
  f.set("rehabCost", v);
  if (!mirrored.value && bothEmpty && v != null) f.set("constructionLoanBudget", v);
  mirrored.value = true;
};
const setBudget = (v: number | null) => {
  const bothEmpty = empty(f.get("rehabCost")) && empty(f.get("constructionLoanBudget"));
  f.set("constructionLoanBudget", v);
  if (!mirrored.value && bothEmpty && v != null) f.set("rehabCost", v);
  mirrored.value = true;
};

const stolenLabel = computed(() =>
  calc.value.stolenMoney != null && calc.value.stolenMoney < 0 ? "Extra out of pocket (rehab beyond budget)" : "Stolen Money (draw spread)",
);
</script>

<template>
  <LifecycleSection title="Rehab" icon="pi-wrench" :surface="surface">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <MoneyInput
        data-testid="form.field.rehabCost"
        :model-value="f.get('rehabCost')"
        @update:model-value="setRehab"
        label="Actual Rehab Cost"
        :inThousands="true"
        :info="impactText('rehabCost')"
      />
      <MoneyInput
        data-testid="form.field.constructionLoanBudget"
        :model-value="f.get('constructionLoanBudget')"
        @update:model-value="setBudget"
        label="Construction Loan Budget"
        :inThousands="true"
        :info="impactText('constructionLoanBudget')"
        :note="calc.hmlAmount == null ? undefined : `HML total ${formatMoney(calc.hmlAmount)}`"
      />
      <NumberInput
        data-testid="form.field.rehabContingency"
        :model-value="f.get('rehabContingency')"
        @update:model-value="(v: number | null) => f.set('rehabContingency', v)"
        label="Contingency"
        suffix="%"
        :min="0"
        :max="100"
        :info="impactText('rehabContingency')"
        :note="calc.rehabCostWithContingency == null ? undefined : `rehab ${formatMoney(calc.rehabCostWithContingency)}`"
      />
      <MoneyInput
        data-testid="form.field.rehabCushion"
        :model-value="f.get('rehabCushion')"
        @update:model-value="(v: number | null) => f.set('rehabCushion', v)"
        label="Rehab Cushion"
        :info="impactText('rehabCushion')"
      />
    </div>
    <template #footer>
      <AutoFigure data-testid="form.auto.stolenMoney" :label="stolenLabel" :value="calc.stolenMoney" hint="construction budget − actual rehab (with contingency)" signed />
    </template>
  </LifecycleSection>
</template>
