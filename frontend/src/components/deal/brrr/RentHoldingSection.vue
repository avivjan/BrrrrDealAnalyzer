<script setup lang="ts">
/**
 * BRRRR › Rent & Holding: the tenant, the pre-refi rent, and the carrying costs until the refi.
 *
 * Taxes and insurance are paid as the bills and deposits they really are: this year's tax bill
 * fills the property's tax bucket on each 15th, and the insurance bill at purchase is paid inside
 * or outside that closing. Their regular-year monthly figures (after the refi) are on Refinance.
 */
import { computed, useId } from "vue";
import type { DealInputModel, InsurancePurchaseBillPaymentTiming } from "../../../types";
import { useDealField, type DealInputFieldKey } from "../../../composables/useDealField";
import { brrrAutoCalc } from "../../../utils/brrrAutoCalc";
import { impactText } from "../../../config/brrrInputImpacts";
import { formatMoney } from "../../../utils/money";
import MoneyInput from "../../ui/MoneyInput.vue";
import NumberInput from "../../ui/NumberInput.vue";
import AutoDefaultMoneyInput from "../../ui/AutoDefaultMoneyInput.vue";
import InputInfo from "../../ui/InputInfo.vue";
import DaysOrDateField from "../../ui/DaysOrDateField.vue";
import LifecycleSection from "../LifecycleSection.vue";
import AutoFigure from "../AutoFigure.vue";

const props = defineProps<{
  deal: DealInputModel;
  surface: "card" | "panel";
  /** Why a field's value is wrong, by field key (`utils/dealInputValidation`); a field with no entry is fine. */
  fieldErrorMessages?: Partial<Record<DealInputFieldKey, string>>;
}>();
const field = useDealField(props.deal);
const autoCalc = computed(() => brrrAutoCalc(props.deal));

const insurancePurchaseBillPaymentTimingId = useId();
const onInsurancePurchaseBillPaymentTiming = (event: Event) => {
  props.deal.insurancePurchaseBillPaymentTiming = (event.target as HTMLSelectElement).value as InsurancePurchaseBillPaymentTiming;
};
const taxBucketDepositHint = computed(() => {
  const depositsUntilRefi = autoCalc.value.propertyTaxBucketFirstBillDepositCountUntilRefi;
  const depositsUntilNovember30 = autoCalc.value.propertyTaxBucketDepositCountUntilFirstPayment;
  if (depositsUntilRefi == null) return undefined;
  if (depositsUntilNovember30 == null) return `no closing date: one deposit every 30 days until the refi`;
  return `${depositsUntilRefi} of ${depositsUntilNovember30} deposits (each 15th to Nov 30) fall before the refi`;
});
const insuranceUntilRefiNote = computed(() =>
  autoCalc.value.insurancePaidMonthlyUntilRefi ? `= ${formatMoney(autoCalc.value.insurancePaidMonthlyUntilRefi)}` : undefined,
);

const preRefiRentHint = computed(() =>
  autoCalc.value.rentCollectionCountBeforeRefi == null ? undefined
    : autoCalc.value.rentCollectionCountBeforeRefi > 0 ? `${autoCalc.value.rentCollectionCountBeforeRefi} rent payments on the 1sts before the refi` : "no 1st between the tenant and the refi",
);
</script>

<template>
  <LifecycleSection title="Rent & Holding" icon="pi-key" :surface="surface">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <MoneyInput
        data-testid="form.field.rent"
        :error-message="fieldErrorMessages?.rent"
        :model-value="field.get('rent')"
        @update:model-value="(v: number | null) => field.set('rent', v)"
        label="Monthly Rent"
        :required="true"
        :needed-to-run-analysis="true"
        :info="impactText('rent')"
      />
      <DaysOrDateField
        data-testid="form.field.daysUntilRented"
        :error-message="fieldErrorMessages?.daysUntilRented"
        :model-value="field.get('daysUntilRented')"
        @update:model-value="(v: number | null) => field.set('daysUntilRented', v)"
        label="Until Tenant Occupied"
        date-label="Tenant occupied"
        :anchor-date="field.getStr('buyClosingDate')"
        :min="0"
        :info="impactText('daysUntilRented')"
      />
      <MoneyInput
        data-testid="form.field.monthlyUtilitiesUntilRented"
        :error-message="fieldErrorMessages?.monthlyUtilitiesUntilRented"
        :model-value="field.get('monthlyUtilitiesUntilRented')"
        @update:model-value="(v: number | null) => field.set('monthlyUtilitiesUntilRented', v)"
        label="Utilities until Rented (per month)"
        :info="impactText('monthlyUtilitiesUntilRented')"
        :note="autoCalc.utilitiesUntilRented == null ? undefined : `= ${formatMoney(autoCalc.utilitiesUntilRented)}`"
      />
      <MoneyInput
        data-testid="form.field.maintenanceBeforeRefi"
        :error-message="fieldErrorMessages?.maintenanceBeforeRefi"
        :model-value="field.get('maintenanceBeforeRefi')"
        @update:model-value="(v: number | null) => field.set('maintenanceBeforeRefi', v)"
        label="Maintenance before Refi"
        :info="impactText('maintenanceBeforeRefi')"
      />
      <MoneyInput
        data-testid="form.field.appliances"
        :error-message="fieldErrorMessages?.appliances"
        :model-value="field.get('appliances')"
        @update:model-value="(v: number | null) => field.set('appliances', v)"
        label="Appliances"
        :info="impactText('appliances')"
      />
      <div class="hidden md:block"></div>

      <MoneyInput
        data-testid="form.field.annual_property_taxes"
        :error-message="fieldErrorMessages?.annual_property_taxes"
        :model-value="field.get('annual_property_taxes')"
        @update:model-value="(v: number | null) => field.set('annual_property_taxes', v)"
        label="Property Tax Bill (this year)"
        :needed-to-run-analysis="true"
        :info="impactText('annual_property_taxes')"
        :note="autoCalc.monthlyPropertyTaxAfterRefi == null ? undefined : `× 0.96 on Nov 30`"
      />
      <div class="flex flex-col gap-1">
        <AutoDefaultMoneyInput
          data-testid="form.field.monthlyPropertyTaxBucketDeposit"
          :error-message="fieldErrorMessages?.monthlyPropertyTaxBucketDeposit"
          :model-value="field.getNullable('monthlyPropertyTaxBucketDeposit')"
          :computed-default="autoCalc.propertyTaxBucketDepositDefault"
          @update:model-value="(v: number | null) => field.setNullable('monthlyPropertyTaxBucketDeposit', v)"
          label="Tax Bucket Deposit (each 15th)"
          :info="impactText('monthlyPropertyTaxBucketDeposit')"
        />
        <p v-if="taxBucketDepositHint" data-testid="form.auto.taxBucketDepositCount" class="numeric text-xs text-fg-muted">{{ taxBucketDepositHint }}</p>
      </div>
      <MoneyInput
        data-testid="form.field.annual_insurance"
        :error-message="fieldErrorMessages?.annual_insurance"
        :model-value="field.get('annual_insurance')"
        @update:model-value="(v: number | null) => field.set('annual_insurance', v)"
        label="Insurance Bill at Purchase"
        :needed-to-run-analysis="true"
        :info="impactText('annual_insurance')"
      />
      <div class="flex flex-col gap-1.5" data-testid="form.field.insurancePurchaseBillPaymentTiming">
        <div data-part="label-row" class="flex h-5 items-center gap-1">
          <label :for="insurancePurchaseBillPaymentTimingId" data-part="label" class="text-sm font-medium leading-5 text-fg">Insurance Bill Paid</label>
          <InputInfo :content="impactText('insurancePurchaseBillPaymentTiming')" field-label="Insurance Bill Paid" />
        </div>
        <select :id="insurancePurchaseBillPaymentTimingId" data-part="select" class="ui-select"
                :value="deal.insurancePurchaseBillPaymentTiming ?? 'inside_purchase_closing'" @change="onInsurancePurchaseBillPaymentTiming">
          <option value="inside_purchase_closing">Inside the purchase closing</option>
          <option value="outside_purchase_closing">Outside the purchase closing</option>
        </select>
      </div>
      <MoneyInput
        data-testid="form.field.monthlyInsuranceUntilRefi"
        :error-message="fieldErrorMessages?.monthlyInsuranceUntilRefi"
        :model-value="field.get('monthlyInsuranceUntilRefi')"
        @update:model-value="(v: number | null) => field.set('monthlyInsuranceUntilRefi', v)"
        label="Insurance per Month until Refi"
        :info="impactText('monthlyInsuranceUntilRefi')"
        :note="insuranceUntilRefiNote"
      />
      <MoneyInput
        data-testid="form.field.montly_hoa"
        :error-message="fieldErrorMessages?.montly_hoa"
        :model-value="field.get('montly_hoa')"
        @update:model-value="(v: number | null) => field.set('montly_hoa', v)"
        label="Monthly HOA"
        :info="impactText('montly_hoa')"
      />

      <div class="md:col-span-2 mt-2 grid grid-cols-2 gap-3 md:grid-cols-4">
        <NumberInput
          data-testid="form.field.vacancyPercent"
          :error-message="fieldErrorMessages?.vacancyPercent"
          :model-value="field.get('vacancyPercent')"
          @update:model-value="(v: number | null) => field.set('vacancyPercent', v)"
          label="Vacancy"
          suffix="%"
          :info="impactText('vacancyPercent')"
        />
        <NumberInput
          data-testid="form.field.maintenancePercent"
          :error-message="fieldErrorMessages?.maintenancePercent"
          :model-value="field.get('maintenancePercent')"
          @update:model-value="(v: number | null) => field.set('maintenancePercent', v)"
          label="Maint."
          suffix="%"
          :info="impactText('maintenancePercent')"
        />
        <NumberInput
          data-testid="form.field.capexPercent"
          :error-message="fieldErrorMessages?.capexPercent"
          :model-value="field.get('capexPercent')"
          @update:model-value="(v: number | null) => field.set('capexPercent', v)"
          label="CapEx"
          suffix="%"
          :info="impactText('capexPercent')"
        />
        <NumberInput
          data-testid="form.field.property_managment_fee_precentages_from_rent"
          :error-message="fieldErrorMessages?.property_managment_fee_precentages_from_rent"
          :model-value="field.get('property_managment_fee_precentages_from_rent')"
          @update:model-value="(v: number | null) => field.set('property_managment_fee_precentages_from_rent', v)"
          label="Prop. Mgmt"
          suffix="%"
          :info="impactText('property_managment_fee_precentages_from_rent')"
        />
      </div>
    </div>
    <template #footer>
      <AutoFigure data-testid="form.auto.preRefiRentalIncome" label="Pre-Refi Rental Income" :value="autoCalc.preRefiRentalIncome" :hint="preRefiRentHint" />
    </template>
  </LifecycleSection>
</template>
