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
const field = useDealField(props.deal);
const autoCalc = computed(() => brrrAutoCalc(props.deal));

const UNDERWRITING_PRESETS = [
  { label: "MyLoanPathway", value: 2240 },
  { label: "Clear2Mortgage", value: 1500 },
  { label: "Cake Mortgage", value: 2195 },
];

const notaryId = useId();
const otherClosingCostsNoteId = useId();
const NOTARY_FEE_DEFAULT = 250;
const moneyNote = (amount: number | null) => (amount == null ? undefined : `= ${formatMoney(amount)}`);
const prepaidInterestHint = computed(() =>
  autoCalc.value.prepaidDaysRefi != null && autoCalc.value.refiClosingDate ? `${autoCalc.value.prepaidDaysRefi} days from ${autoCalc.value.refiClosingDate} through month end` : undefined,
);
</script>

<template>
  <LifecycleSection title="Refinance" icon="pi-refresh" :surface="surface">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <DaysOrDateField
        data-testid="form.field.daysUntilRefi"
        :model-value="field.get('daysUntilRefi')"
        @update:model-value="(v: number | null) => field.set('daysUntilRefi', v)"
        label="Days to Refi"
        date-label="Refi closing date"
        :anchor-date="field.getStr('buyClosingDate')"
        :min="1"
        :required="true"
        :info="impactText('daysUntilRefi')"
      />
      <AutoFigure data-testid="form.auto.prepaidInterestRefi" label="Prepaid Interest (Refi)" :value="autoCalc.prepaidInterestRefi" :hint="prepaidInterestHint" />

      <MoneyInput
        data-testid="form.field.arv_in_thousands"
        :model-value="field.get('arv_in_thousands')"
        @update:model-value="(v: number | null) => field.set('arv_in_thousands', v)"
        label="ARV"
        :inThousands="true"
        :required="true"
        :info="impactText('arv_in_thousands')"
      />
      <AutoDefaultMoneyInput
        data-testid="form.field.lowestArv"
        :model-value="field.getNullable('lowestArv')"
        :computed-default="autoCalc.lowestArvDefault == null ? null : autoCalc.lowestArvDefault / 1000"
        @update:model-value="(v: number | null) => field.setNullable('lowestArv', v)"
        label="Lowest ARV Possible (stress test)"
        :inThousands="true"
        :info="impactText('lowestArv')"
      />
      <SliderField
        data-testid="form.field.ltv_as_precent"
        :model-value="field.get('ltv_as_precent')"
        @update:model-value="(v: number | null) => field.set('ltv_as_precent', v)"
        label="LTV"
        :min="0"
        :max="100"
        :sliderMin="1"
        :sliderMax="100"
        :step="0.1"
        suffix="%"
        :required="true"
        :info="impactText('ltv_as_precent')"
        :note="autoCalc.refiLoanAmount == null ? undefined : `loan ${formatMoney(autoCalc.refiLoanAmount)}`"
      />
      <SliderField
        data-testid="form.field.interestRate"
        :model-value="field.get('interestRate')"
        @update:model-value="(v: number | null) => field.set('interestRate', v)"
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
        :model-value="field.get('loanTermYears')"
        @update:model-value="(v: number | null) => field.set('loanTermYears', v)"
        label="Loan Term"
        suffix=" Years"
        :info="impactText('loanTermYears')"
      />
      <AutoFigure data-testid="form.auto.conservativeRefiLoan" label="Refi loan at the lowest ARV" :value="autoCalc.conservativeRefiLoanAmount" />

      <!-- Closing costs (refi) -->
      <div class="my-2 border-t border-line pt-4 md:col-span-2">
        <UiSectionHeader as="h4" class="mb-3">Closing Costs (Refi)</UiSectionHeader>
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <MoneyInput
            data-testid="form.field.loanChargesRefi"
            :model-value="field.get('loanChargesRefi')"
            @update:model-value="(v: number | null) => field.set('loanChargesRefi', v)"
            label="Loan Charges (Refi)"
            :info="impactText('loanChargesRefi')"
          />
          <AutoDefaultMoneyInput
            data-testid="form.field.recordingTransferRefi"
            :model-value="field.getNullable('recordingTransferRefi')"
            :computed-default="autoCalc.recordingTransferRefiDefault"
            @update:model-value="(v: number | null) => field.setNullable('recordingTransferRefi', v)"
            label="Recording & Transfer (Refi)"
            :info="impactText('recordingTransferRefi')"
          />
          <AutoDefaultMoneyInput
            data-testid="form.field.titleEscrowRefi"
            :model-value="field.getNullable('titleEscrowRefi')"
            :computed-default="autoCalc.titleEscrowRefiDefault"
            @update:model-value="(v: number | null) => field.setNullable('titleEscrowRefi', v)"
            label="Title & Escrow / Settlement (Refi)"
            :info="impactText('titleEscrowRefi')"
          />
          <div class="flex flex-col gap-2 rounded-ctl border-ui border-line p-3 group-data-[surface=card]:bg-surface-2 group-data-[surface=panel]:bg-surface" data-testid="form.field.onlineNotaryRefi">
            <div class="flex items-center gap-2">
              <input :id="notaryId" type="checkbox" class="h-4 w-4 accent-primary" :checked="field.getBool('onlineNotaryRefi', true)"
                     @change="field.setBool('onlineNotaryRefi', ($event.target as HTMLInputElement).checked)" />
              <label :for="notaryId" class="text-sm font-medium text-fg">Online notary</label>
              <InputInfo :content="impactText('onlineNotaryRefi')" field-label="Online notary" />
            </div>
            <AutoDefaultMoneyInput
              v-if="field.getBool('onlineNotaryRefi', true)"
              data-testid="form.field.onlineNotaryFeeRefi"
              :model-value="field.getNullable('onlineNotaryFeeRefi')"
              :computed-default="NOTARY_FEE_DEFAULT"
              @update:model-value="(v: number | null) => field.setNullable('onlineNotaryFeeRefi', v)"
              label="Notary fee"
              :info="impactText('onlineNotaryFeeRefi')"
            />
          </div>
          <MoneyInput
            data-testid="form.field.appraisalFee"
            :model-value="field.get('appraisalFee')"
            @update:model-value="(v: number | null) => field.set('appraisalFee', v)"
            label="Appraisal"
            :info="impactText('appraisalFee')"
          />
          <MoneyInput
            data-testid="form.field.surveyFee"
            :model-value="field.get('surveyFee')"
            @update:model-value="(v: number | null) => field.set('surveyFee', v)"
            label="Survey"
            :info="impactText('surveyFee')"
            note="$385 · $450 · $485 seen"
          />
          <PresetSelectInput
            data-testid="form.field.refiUnderwritingFee"
            :model-value="field.get('refiUnderwritingFee')"
            @update:model-value="(v: number | null) => field.set('refiUnderwritingFee', v)"
            label="Underwriting Fee"
            :presets="UNDERWRITING_PRESETS"
            :info="impactText('refiUnderwritingFee')"
          />
          <NumberInput
            data-testid="form.field.refiPoints"
            :model-value="field.get('refiPoints')"
            @update:model-value="(v: number | null) => field.set('refiPoints', v)"
            label="Broker Points"
            suffix=" pts"
            :min="0"
            :max="100"
            :info="impactText('refiPoints')"
            :note="moneyNote(autoCalc.brokerPointsDollars)"
          />
          <div class="flex items-end gap-2">
            <MoneyInput
              data-testid="form.field.brokerProcessingFeeRefi"
              class="min-w-0 flex-1"
              :model-value="field.get('brokerProcessingFeeRefi')"
              @update:model-value="(v: number | null) => field.set('brokerProcessingFeeRefi', v)"
              label="Broker Processing Fee"
              :info="impactText('brokerProcessingFeeRefi')"
            />
            <UiButton type="button" data-testid="form.processing-zero" variant="secondary" size="sm" class="touch:min-h-11" @click="field.set('brokerProcessingFeeRefi', 0)">$0</UiButton>
          </div>
          <div class="flex flex-col gap-1.5">
            <MoneyInput
              data-testid="form.field.otherClosingCostsRefi"
              :model-value="field.get('otherClosingCostsRefi')"
              @update:model-value="(v: number | null) => field.set('otherClosingCostsRefi', v)"
              label="Other Closing Costs (Refi)"
              :info="impactText('otherClosingCostsRefi')"
            />
            <input
              :id="otherClosingCostsNoteId"
              data-testid="form.field.otherClosingCostsRefiNote"
              type="text"
              maxlength="500"
              class="ui-input text-xs"
              placeholder="What is it for?"
              aria-label="What the other refi closing costs are for"
              :value="field.getStr('otherClosingCostsRefiNote') ?? ''"
              @change="field.setStr('otherClosingCostsRefiNote', ($event.target as HTMLInputElement).value || null)"
            />
          </div>
        </div>
        <div class="mt-3">
          <AutoFigure data-testid="form.auto.closingCostsRefiTotal" label="Total closing costs (Refi)" :value="autoCalc.closingCostsRefiTotal" />
        </div>
      </div>

      <!-- Reserves -->
      <div class="my-2 border-t border-line pt-4 md:col-span-2">
        <UiSectionHeader as="h4" class="mb-3">Reserves escrowed at refi</UiSectionHeader>
        <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
          <MoneyInput
            data-testid="form.field.maintenanceReserve"
            :model-value="field.get('maintenanceReserve')"
            @update:model-value="(v: number | null) => field.set('maintenanceReserve', v)"
            label="Maintenance Reserve"
            :info="impactText('maintenanceReserve')"
          />
          <AutoDefaultMoneyInput
            data-testid="form.field.vacancyReserve"
            :model-value="field.getNullable('vacancyReserve')"
            :computed-default="autoCalc.vacancyReserveDefault"
            @update:model-value="(v: number | null) => field.setNullable('vacancyReserve', v)"
            label="Vacancy Reserve (1 month rent)"
            :info="impactText('vacancyReserve')"
          />
          <MoneyInput
            data-testid="form.field.capexReserve"
            :model-value="field.get('capexReserve')"
            @update:model-value="(v: number | null) => field.set('capexReserve', v)"
            label="CapEx Reserve"
            :info="impactText('capexReserve')"
          />
        </div>
        <div class="mt-3">
          <AutoFigure data-testid="form.auto.reservesTotal" label="Total reserves" :value="autoCalc.reservesTotal" />
        </div>
      </div>
    </div>
    <template #footer>
      <AutoFigure data-testid="form.auto.hmlPayoff" label="HML payoff at refi" :value="autoCalc.hmlPayoff" hint="principal + interest accrued since the 1st" />
      <AutoFigure data-testid="form.auto.cashOutWire" label="Cash-Out Routi" :value="autoCalc.cashOutWire" hint="negative = cash brought to the table" signed />
      <AutoFigure data-testid="form.auto.cashOutWireConservative" label="Cash-Out Routi (Lowest ARV)" :value="autoCalc.cashOutWireConservative" signed />
    </template>
  </LifecycleSection>
</template>
