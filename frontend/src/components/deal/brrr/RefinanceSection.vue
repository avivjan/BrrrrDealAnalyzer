<script setup lang="ts">
/**
 * BRRRR › Refinance: the new loan, its settlement lines (the insurance bill and the tax lump when
 * the lender collects them), what is paid outside the closing, the regular-year insurance, the
 * reserves the owner sets aside, and the two wires. The wires are the settlement statement's
 * "Due to Borrower": the reserves are the owner's own money and never come off them.
 */
import { computed, useId } from "vue";
import type { DealInputModel, InsuranceRefiBillPaymentTiming, PropertyTaxCollectionAtRefi } from "../../../types";
import { useDealField, type NumericKey } from "../../../composables/useDealField";
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

const props = defineProps<{
  deal: DealInputModel;
  surface: "card" | "panel";
  /** Why a field's value is wrong, by field key (`utils/dealInputValidation`); a field with no entry is fine. */
  fieldErrorMessages?: Partial<Record<NumericKey, string>>;
}>();
const field = useDealField(props.deal);
const autoCalc = computed(() => brrrAutoCalc(props.deal));

const UNDERWRITING_PRESETS = [
  { label: "MyLoanPathway", value: 2240 },
  { label: "Clear2Mortgage", value: 1500 },
  { label: "Cake Mortgage", value: 2195 },
];

const notaryId = useId();
const otherClosingCostsNoteId = useId();
const insuranceRefiBillPaymentTimingId = useId();
const propertyTaxCollectionAtRefiId = useId();
const onInsuranceRefiBillPaymentTiming = (event: Event) => {
  props.deal.insuranceRefiBillPaymentTiming = (event.target as HTMLSelectElement).value as InsuranceRefiBillPaymentTiming;
};
const onPropertyTaxCollectionAtRefi = (event: Event) => {
  props.deal.propertyTaxCollectionAtRefi = (event.target as HTMLSelectElement).value as PropertyTaxCollectionAtRefi;
};
const fullTaxBillCollectedAtRefi = computed(() => props.deal.propertyTaxCollectionAtRefi === "full_tax_bill_collected_at_refi");
const NOTARY_FEE_DEFAULT = 250;
/** $0 by default (the owner's brokers rarely charge one); this quick button sets the typical fee. */
const BROKER_PROCESSING_FEE_TYPICAL = 395;
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
        :error-message="fieldErrorMessages?.daysUntilRefi"
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
        :error-message="fieldErrorMessages?.arv_in_thousands"
        :model-value="field.get('arv_in_thousands')"
        @update:model-value="(v: number | null) => field.set('arv_in_thousands', v)"
        label="ARV"
        :inThousands="true"
        :required="true"
        :needed-to-run-analysis="true"
        :info="impactText('arv_in_thousands')"
      />
      <AutoDefaultMoneyInput
        data-testid="form.field.lowestArv"
        :error-message="fieldErrorMessages?.lowestArv"
        :model-value="field.getNullable('lowestArv')"
        :computed-default="autoCalc.lowestArvDefault == null ? null : autoCalc.lowestArvDefault / 1000"
        @update:model-value="(v: number | null) => field.setNullable('lowestArv', v)"
        label="Lowest ARV Possible (stress test)"
        :inThousands="true"
        :info="impactText('lowestArv')"
      />
      <SliderField
        data-testid="form.field.ltv_as_precent"
        :error-message="fieldErrorMessages?.ltv_as_precent"
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
        :error-message="fieldErrorMessages?.interestRate"
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
        :error-message="fieldErrorMessages?.loanTermYears"
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
            :error-message="fieldErrorMessages?.loanChargesRefi"
            :model-value="field.get('loanChargesRefi')"
            @update:model-value="(v: number | null) => field.set('loanChargesRefi', v)"
            label="Loan Charges (Refi)"
            :info="impactText('loanChargesRefi')"
          />
          <AutoDefaultMoneyInput
            data-testid="form.field.recordingTransferRefi"
            :error-message="fieldErrorMessages?.recordingTransferRefi"
            :model-value="field.getNullable('recordingTransferRefi')"
            :computed-default="autoCalc.recordingTransferRefiDefault"
            @update:model-value="(v: number | null) => field.setNullable('recordingTransferRefi', v)"
            label="Recording & Transfer (Refi)"
            :info="impactText('recordingTransferRefi')"
          />
          <AutoDefaultMoneyInput
            data-testid="form.field.titleEscrowRefi"
            :error-message="fieldErrorMessages?.titleEscrowRefi"
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
              :error-message="fieldErrorMessages?.onlineNotaryFeeRefi"
              :model-value="field.getNullable('onlineNotaryFeeRefi')"
              :computed-default="NOTARY_FEE_DEFAULT"
              @update:model-value="(v: number | null) => field.setNullable('onlineNotaryFeeRefi', v)"
              label="Notary fee"
              :info="impactText('onlineNotaryFeeRefi')"
            />
          </div>
          <PresetSelectInput
            data-testid="form.field.refiUnderwritingFee"
            :error-message="fieldErrorMessages?.refiUnderwritingFee"
            :model-value="field.get('refiUnderwritingFee')"
            @update:model-value="(v: number | null) => field.set('refiUnderwritingFee', v)"
            label="Underwriting Fee"
            :presets="UNDERWRITING_PRESETS"
            :info="impactText('refiUnderwritingFee')"
          />
          <NumberInput
            data-testid="form.field.refiPoints"
            :error-message="fieldErrorMessages?.refiPoints"
            :model-value="field.get('refiPoints')"
            @update:model-value="(v: number | null) => field.set('refiPoints', v)"
            label="Broker Points"
            suffix=" pts"
            :info="impactText('refiPoints')"
            :note="moneyNote(autoCalc.brokerPointsDollars)"
          />
          <div class="flex items-end gap-2">
            <MoneyInput
              data-testid="form.field.brokerProcessingFeeRefi"
              :error-message="fieldErrorMessages?.brokerProcessingFeeRefi"
              class="min-w-0 flex-1"
              :model-value="field.get('brokerProcessingFeeRefi')"
              @update:model-value="(v: number | null) => field.set('brokerProcessingFeeRefi', v)"
              label="Broker Processing Fee"
              :info="impactText('brokerProcessingFeeRefi')"
            />
            <UiButton type="button" data-testid="form.processing-395" variant="secondary" size="sm" class="touch:min-h-11" title="The usual broker processing fee" @click="field.set('brokerProcessingFeeRefi', BROKER_PROCESSING_FEE_TYPICAL)">$395</UiButton>
          </div>
          <div class="flex flex-col gap-1.5">
            <MoneyInput
              data-testid="form.field.otherClosingCostsRefi"
              :error-message="fieldErrorMessages?.otherClosingCostsRefi"
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
          <AutoDefaultMoneyInput
            data-testid="form.field.insuranceBillAtRefiClosing"
            :error-message="fieldErrorMessages?.insuranceBillAtRefiClosing"
            :model-value="field.getNullable('insuranceBillAtRefiClosing')"
            :computed-default="autoCalc.insuranceBillAtRefiDefault"
            @update:model-value="(v: number | null) => field.setNullable('insuranceBillAtRefiClosing', v)"
            label="Insurance Bill at Refi"
            :info="impactText('insuranceBillAtRefiClosing')"
          />
          <div class="flex flex-col gap-1.5" data-testid="form.field.insuranceRefiBillPaymentTiming">
            <div data-part="label-row" class="flex h-5 items-center gap-1">
              <label :for="insuranceRefiBillPaymentTimingId" data-part="label" class="text-sm font-medium leading-5 text-fg">Insurance Bill at Refi Paid</label>
              <InputInfo :content="impactText('insuranceRefiBillPaymentTiming')" field-label="Insurance Bill at Refi Paid" />
            </div>
            <select :id="insuranceRefiBillPaymentTimingId" data-part="select" class="ui-select"
                    :value="deal.insuranceRefiBillPaymentTiming ?? 'inside_refi_closing'" @change="onInsuranceRefiBillPaymentTiming">
              <option value="inside_refi_closing">Inside the refi closing</option>
              <option value="outside_refi_closing">Outside the refi closing</option>
            </select>
          </div>
          <div class="flex flex-col gap-1.5" data-testid="form.field.propertyTaxCollectionAtRefi">
            <div data-part="label-row" class="flex h-5 items-center gap-1">
              <label :for="propertyTaxCollectionAtRefiId" data-part="label" class="text-sm font-medium leading-5 text-fg">Property Tax at Refi</label>
              <InputInfo :content="impactText('propertyTaxCollectionAtRefi')" field-label="Property Tax at Refi" />
            </div>
            <select :id="propertyTaxCollectionAtRefiId" data-part="select" class="ui-select"
                    :value="deal.propertyTaxCollectionAtRefi ?? 'no_tax_collected_at_refi'" @change="onPropertyTaxCollectionAtRefi">
              <option value="no_tax_collected_at_refi">My tax bucket pays the Nov 30 bill</option>
              <option value="full_tax_bill_collected_at_refi">The refi lender collects the whole bill</option>
            </select>
          </div>
          <AutoDefaultMoneyInput
            v-if="fullTaxBillCollectedAtRefi"
            data-testid="form.field.propertyTaxLumpSumAtRefiClosing"
            :error-message="fieldErrorMessages?.propertyTaxLumpSumAtRefiClosing"
            :model-value="field.getNullable('propertyTaxLumpSumAtRefiClosing')"
            :computed-default="autoCalc.propertyTaxLumpSumAtRefiClosingDefault"
            @update:model-value="(v: number | null) => field.setNullable('propertyTaxLumpSumAtRefiClosing', v)"
            label="Tax Lump collected at Refi"
            :info="impactText('propertyTaxLumpSumAtRefiClosing')"
          />
        </div>
        <div class="mt-3">
          <AutoFigure data-testid="form.auto.closingCostsRefiTotal" label="Total closing costs (Refi)" :value="autoCalc.closingCostsRefiTotal" />
        </div>
      </div>

      <!-- Paid outside the refi closing -->
      <div class="my-2 border-t border-line pt-4 md:col-span-2">
        <UiSectionHeader as="h4" class="mb-3">Paid outside closing (end of rehab)</UiSectionHeader>
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <MoneyInput
            data-testid="form.field.appraisalFee"
            :error-message="fieldErrorMessages?.appraisalFee"
            :model-value="field.get('appraisalFee')"
            @update:model-value="(v: number | null) => field.set('appraisalFee', v)"
            label="Appraisal"
            :info="impactText('appraisalFee')"
          />
          <MoneyInput
            data-testid="form.field.surveyFee"
            :error-message="fieldErrorMessages?.surveyFee"
            :model-value="field.get('surveyFee')"
            @update:model-value="(v: number | null) => field.set('surveyFee', v)"
            label="Survey"
            :info="impactText('surveyFee')"
            note="$385 · $450 · $485 seen"
          />
        </div>
      </div>

      <!-- A regular year after the refi -->
      <div class="my-2 border-t border-line pt-4 md:col-span-2">
        <UiSectionHeader as="h4" class="mb-3">Regular year after the refi</UiSectionHeader>
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <AutoDefaultMoneyInput
            data-testid="form.field.monthlyInsuranceAfterRefi"
            :error-message="fieldErrorMessages?.monthlyInsuranceAfterRefi"
            :model-value="field.getNullable('monthlyInsuranceAfterRefi')"
            :computed-default="autoCalc.monthlyInsuranceAfterRefiDefault"
            @update:model-value="(v: number | null) => field.setNullable('monthlyInsuranceAfterRefi', v)"
            label="Insurance per Month after Refi"
            :info="impactText('monthlyInsuranceAfterRefi')"
          />
          <AutoFigure data-testid="form.auto.monthlyPropertyTaxAfterRefi" label="Property tax per month" :value="autoCalc.monthlyPropertyTaxAfterRefi" hint="this year's bill × 0.96 ÷ 12" />
        </div>
      </div>

      <!-- Reserves -->
      <div class="my-2 border-t border-line pt-4 md:col-span-2">
        <UiSectionHeader as="h4" class="mb-3">Reserves you set aside at refi</UiSectionHeader>
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <MoneyInput
            data-testid="form.field.maintenanceReserve"
            :error-message="fieldErrorMessages?.maintenanceReserve"
            :model-value="field.get('maintenanceReserve')"
            @update:model-value="(v: number | null) => field.set('maintenanceReserve', v)"
            label="Maintenance Reserve"
            :info="impactText('maintenanceReserve')"
          />
          <AutoDefaultMoneyInput
            data-testid="form.field.vacancyReserve"
            :error-message="fieldErrorMessages?.vacancyReserve"
            :model-value="field.getNullable('vacancyReserve')"
            :computed-default="autoCalc.vacancyReserveDefault"
            @update:model-value="(v: number | null) => field.setNullable('vacancyReserve', v)"
            label="Vacancy Reserve (1 month rent)"
            :info="impactText('vacancyReserve')"
          />
          <MoneyInput
            data-testid="form.field.capexReserve"
            :error-message="fieldErrorMessages?.capexReserve"
            :model-value="field.get('capexReserve')"
            @update:model-value="(v: number | null) => field.set('capexReserve', v)"
            label="CapEx Reserve"
            :info="impactText('capexReserve')"
          />
          <AutoDefaultMoneyInput
            data-testid="form.field.hysaDepositAtRefi"
            :error-message="fieldErrorMessages?.hysaDepositAtRefi"
            :model-value="field.getNullable('hysaDepositAtRefi')"
            :computed-default="autoCalc.hysaDepositAtRefiDefault"
            @update:model-value="(v: number | null) => field.setNullable('hysaDepositAtRefi', v)"
            label="HYSA Deposit (3 months P&I)"
            :info="impactText('hysaDepositAtRefi')"
          />
        </div>
        <div class="mt-3">
          <AutoFigure data-testid="form.auto.reservesTotal" label="Total reserves" :value="autoCalc.reservesTotal" hint="your money, kept in the deal: not taken off the wire" />
        </div>
      </div>
    </div>
    <template #footer>
      <AutoFigure data-testid="form.auto.hmlPayoff" label="HML payoff at refi" :value="autoCalc.hmlPayoff" hint="principal + interest accrued since the 1st" />
      <AutoFigure data-testid="form.auto.cashOutWire" label="Cash-Out Routi" :value="autoCalc.cashOutWire" hint="the statement's Due to Borrower; negative = cash brought to the table" signed />
      <AutoFigure data-testid="form.auto.cashOutWireConservative" label="Cash-Out Routi (Lowest ARV)" :value="autoCalc.cashOutWireConservative" signed />
    </template>
  </LifecycleSection>
</template>
