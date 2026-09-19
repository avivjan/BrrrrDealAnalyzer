<script setup lang="ts">
/** BRRRR › Refinance: the new loan, its settlement lines, the reserves, and the two wires. */
import { computed, useId } from "vue";
import type { DealInputModel } from "../../../types";
import { useDealField } from "../../../composables/useDealField";
import { brrrAutoCalc } from "../../../utils/brrrAutoCalc";
import { impactText } from "../../../config/brrrInputImpacts";
import { formatMoney } from "../../../utils/money";
import MoneyInput from "../../ui/MoneyInput.vue";
import NumberInput from "../../ui/NumberInput.vue";
import SliderField from "../../ui/SliderField.vue";
import AutoDefaultMoneyInput from "../../ui/AutoDefaultMoneyInput.vue";
import PresetSelectInput from "../../ui/PresetSelectInput.vue";
import DaysOrDateField from "../../ui/DaysOrDateField.vue";
import InputInfo from "../../ui/InputInfo.vue";
import LifecycleSection from "../LifecycleSection.vue";
import AutoFigure from "../AutoFigure.vue";

const props = defineProps<{ deal: DealInputModel; surface: "card" | "panel" }>();
const f = useDealField(props.deal);
const calc = computed(() => brrrAutoCalc(props.deal));

const UNDERWRITING_PRESETS = [
  { label: "MyLoanPathway", value: 2240 },
  { label: "Clear2Mortgage", value: 1500 },
  { label: "Cake Mortgage", value: 2195 },
];

const notaryId = useId();
const money = (v: number | null) => (v == null ? undefined : `= ${formatMoney(v)}`);
const prepaidHint = computed(() =>
  calc.value.prepaidDaysRefi != null && calc.value.refiClosingDate ? `${calc.value.prepaidDaysRefi} days from ${calc.value.refiClosingDate} through month end` : undefined,
);
</script>

<template>
  <LifecycleSection title="Refinance" icon="pi-refresh" :surface="surface">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <DaysOrDateField
        data-testid="form.field.daysUntilRefi"
        :model-value="f.get('daysUntilRefi')"
        @update:model-value="(v: number | null) => f.set('daysUntilRefi', v)"
        label="Days to Refi"
        date-label="Refi closing date"
        :anchor-date="f.getStr('buyClosingDate')"
        :min="1"
        :required="true"
        :info="impactText('daysUntilRefi')"
      />
      <AutoFigure data-testid="form.auto.prepaidInterestRefi" label="Prepaid Interest (Refi)" :value="calc.prepaidInterestRefi" :hint="prepaidHint" />

      <MoneyInput
        data-testid="form.field.arv_in_thousands"
        :model-value="f.get('arv_in_thousands')"
        @update:model-value="(v: number | null) => f.set('arv_in_thousands', v)"
        label="ARV"
        :inThousands="true"
        :required="true"
        :info="impactText('arv_in_thousands')"
      />
      <AutoDefaultMoneyInput
        data-testid="form.field.lowestArv"
        :model-value="f.getNullable('lowestArv')"
        :computed-default="calc.lowestArvDefault == null ? null : calc.lowestArvDefault / 1000"
        @update:model-value="(v: number | null) => f.setNullable('lowestArv', v)"
        label="Lowest ARV Possible (stress test)"
        :inThousands="true"
        :info="impactText('lowestArv')"
      />
      <SliderField
        data-testid="form.field.ltv_as_precent"
        :model-value="f.get('ltv_as_precent')"
        @update:model-value="(v: number | null) => f.set('ltv_as_precent', v)"
        label="LTV"
        :min="0"
        :max="100"
        :sliderMin="1"
        :sliderMax="100"
        :step="0.1"
        suffix="%"
        :required="true"
        :info="impactText('ltv_as_precent')"
        :note="calc.refiLoanAmount == null ? undefined : `loan ${formatMoney(calc.refiLoanAmount)}`"
      />
      <SliderField
        data-testid="form.field.interestRate"
        :model-value="f.get('interestRate')"
        @update:model-value="(v: number | null) => f.set('interestRate', v)"
        label="Long Term Interest Rate"
        :min="0"
        :max="100"
        :sliderMin="3"
        :sliderMax="12"
        :step="0.05"
        suffix="%"
        :required="true"
        :info="impactText('interestRate')"
      />
      <NumberInput
        data-testid="form.field.loanTermYears"
        :model-value="f.get('loanTermYears')"
        @update:model-value="(v: number | null) => f.set('loanTermYears', v)"
        label="Loan Term"
        suffix=" Years"
        :info="impactText('loanTermYears')"
      />
      <AutoFigure data-testid="form.auto.conservativeRefiLoan" label="Refi loan at the lowest ARV" :value="calc.conservativeRefiLoanAmount" />

      <!-- Closing costs (refi) -->
      <div class="my-2 border-t border-line pt-4 md:col-span-2">
        <UiSectionHeader as="h4" class="mb-3">Closing Costs (Refi)</UiSectionHeader>
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <MoneyInput
            data-testid="form.field.loanChargesRefi"
            :model-value="f.get('loanChargesRefi')"
            @update:model-value="(v: number | null) => f.set('loanChargesRefi', v)"
            label="Loan Charges (Refi)"
            :info="impactText('loanChargesRefi')"
          />
          <AutoDefaultMoneyInput
            data-testid="form.field.recordingTransferRefi"
            :model-value="f.getNullable('recordingTransferRefi')"
            :computed-default="calc.recordingTransferRefiDefault"
            @update:model-value="(v: number | null) => f.setNullable('recordingTransferRefi', v)"
            label="Recording & Transfer (Refi)"
            :info="impactText('recordingTransferRefi')"
          />
          <AutoDefaultMoneyInput
            data-testid="form.field.titleEscrowRefi"
            :model-value="f.getNullable('titleEscrowRefi')"
            :computed-default="calc.titleEscrowRefiDefault"
            @update:model-value="(v: number | null) => f.setNullable('titleEscrowRefi', v)"
            label="Title & Escrow / Settlement (Refi)"
            :info="impactText('titleEscrowRefi')"
          />
          <div class="flex items-center gap-2 rounded-ctl border-ui border-line p-3 group-data-[surface=card]:bg-surface-2 group-data-[surface=panel]:bg-surface" data-testid="form.field.onlineNotaryRefi">
            <input :id="notaryId" type="checkbox" class="h-4 w-4 accent-primary" :checked="f.getBool('onlineNotaryRefi', true)"
                   @change="f.setBool('onlineNotaryRefi', ($event.target as HTMLInputElement).checked)" />
            <label :for="notaryId" class="text-sm font-medium text-fg">Online notary (+$250)</label>
            <InputInfo :content="impactText('onlineNotaryRefi')" field-label="Online notary" />
          </div>
          <MoneyInput
            data-testid="form.field.appraisalFee"
            :model-value="f.get('appraisalFee')"
            @update:model-value="(v: number | null) => f.set('appraisalFee', v)"
            label="Appraisal"
            :info="impactText('appraisalFee')"
          />
          <MoneyInput
            data-testid="form.field.surveyFee"
            :model-value="f.get('surveyFee')"
            @update:model-value="(v: number | null) => f.set('surveyFee', v)"
            label="Survey"
            :info="impactText('surveyFee')"
            note="$385 · $450 · $485 seen"
          />
          <PresetSelectInput
            data-testid="form.field.refiUnderwritingFee"
            :model-value="f.get('refiUnderwritingFee')"
            @update:model-value="(v: number | null) => f.set('refiUnderwritingFee', v)"
            label="Underwriting Fee"
            :presets="UNDERWRITING_PRESETS"
            :info="impactText('refiUnderwritingFee')"
          />
          <NumberInput
            data-testid="form.field.refiPoints"
            :model-value="f.get('refiPoints')"
            @update:model-value="(v: number | null) => f.set('refiPoints', v)"
            label="Broker Points"
            suffix=" pts"
            :min="0"
            :max="100"
            :info="impactText('refiPoints')"
            :note="money(calc.brokerPointsDollars)"
          />
          <div class="flex items-end gap-2">
            <MoneyInput
              data-testid="form.field.brokerProcessingFeeRefi"
              class="min-w-0 flex-1"
              :model-value="f.get('brokerProcessingFeeRefi')"
              @update:model-value="(v: number | null) => f.set('brokerProcessingFeeRefi', v)"
              label="Broker Processing Fee"
              :info="impactText('brokerProcessingFeeRefi')"
            />
            <UiButton type="button" data-testid="form.processing-zero" variant="secondary" size="sm" class="touch:min-h-11" @click="f.set('brokerProcessingFeeRefi', 0)">$0</UiButton>
          </div>
          <MoneyInput
            data-testid="form.field.otherClosingCostsRefi"
            :model-value="f.get('otherClosingCostsRefi')"
            @update:model-value="(v: number | null) => f.set('otherClosingCostsRefi', v)"
            label="Other Closing Costs (Refi)"
            :info="impactText('otherClosingCostsRefi')"
          />
        </div>
        <div class="mt-3">
          <AutoFigure data-testid="form.auto.closingCostsRefiTotal" label="Total closing costs (Refi)" :value="calc.closingCostsRefiTotal" />
        </div>
      </div>

      <!-- Reserves -->
      <div class="my-2 border-t border-line pt-4 md:col-span-2">
        <UiSectionHeader as="h4" class="mb-3">Reserves escrowed at refi</UiSectionHeader>
        <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
          <MoneyInput
            data-testid="form.field.maintenanceReserve"
            :model-value="f.get('maintenanceReserve')"
            @update:model-value="(v: number | null) => f.set('maintenanceReserve', v)"
            label="Maintenance Reserve"
            :info="impactText('maintenanceReserve')"
          />
          <AutoDefaultMoneyInput
            data-testid="form.field.vacancyReserve"
            :model-value="f.getNullable('vacancyReserve')"
            :computed-default="calc.vacancyReserveDefault"
            @update:model-value="(v: number | null) => f.setNullable('vacancyReserve', v)"
            label="Vacancy Reserve (1 month rent)"
            :info="impactText('vacancyReserve')"
          />
          <MoneyInput
            data-testid="form.field.capexReserve"
            :model-value="f.get('capexReserve')"
            @update:model-value="(v: number | null) => f.set('capexReserve', v)"
            label="CapEx Reserve"
            :info="impactText('capexReserve')"
          />
        </div>
        <div class="mt-3">
          <AutoFigure data-testid="form.auto.reservesTotal" label="Total reserves" :value="calc.reservesTotal" />
        </div>
      </div>
    </div>
    <template #footer>
      <AutoFigure data-testid="form.auto.hmlPayoff" label="HML payoff at refi" :value="calc.hmlPayoff" hint="principal + interest accrued since the 1st" />
      <AutoFigure data-testid="form.auto.cashOutWire" label="Cash-Out Wire (Refi)" :value="calc.cashOutWire" hint="negative = cash brought to the table" signed />
      <AutoFigure data-testid="form.auto.cashOutWireConservative" label="Cash-Out Wire at the lowest ARV" :value="calc.cashOutWireConservative" signed />
    </template>
  </LifecycleSection>
</template>
