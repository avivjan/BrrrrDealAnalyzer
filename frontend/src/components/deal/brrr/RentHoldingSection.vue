<script setup lang="ts">
/**
 * BRRRR › Rent & Holding: the tenant, the pre-refi rent, and the carrying costs until the refi.
 *
 * Taxes and insurance are paid as the bills and deposits they really are: this year's tax bill
 * fills the property's tax bucket on each 15th (the insurance bill at purchase is on Buy, a line of
 * that settlement). The monthly reserves (a % of the rent or dollars per month) and the
 * regular-year insurance and tax after the refi close the section.
 */
import { computed } from "vue";
import type { DealInputModel } from "../../../types";
import { useDealField, type DealInputFieldKey } from "../../../composables/useDealField";
import { brrrAutoCalc } from "../../../utils/brrrAutoCalc";
import { impactText } from "../../../config/brrrInputImpacts";
import { formatMoney } from "../../../utils/money";
import MoneyInput from "../../ui/MoneyInput.vue";
import AutoDefaultMoneyInput from "../../ui/AutoDefaultMoneyInput.vue";
import PercentOfRentOrMonthlyDollarsInput from "../../ui/PercentOfRentOrMonthlyDollarsInput.vue";
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

const monthlyRentDollars = computed(() => field.get("rent"));
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

      <!-- Monthly reserves of a regular year: a % of the rent or dollars per month -->
      <div class="my-2 border-t border-line pt-4 md:col-span-2">
        <UiSectionHeader as="h4" class="mb-3">Monthly reserves</UiSectionHeader>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <PercentOfRentOrMonthlyDollarsInput
            data-testid="form.field.vacancyPercent"
            label="Vacancy"
            :percent-of-rent="field.get('vacancyPercent')"
            :monthly-dollars="field.getNullable('monthlyVacancyReserveDollars')"
            :monthly-rent-dollars="monthlyRentDollars"
            :info="impactText('vacancyPercent')"
            :percent-error-message="fieldErrorMessages?.vacancyPercent"
            :dollars-error-message="fieldErrorMessages?.monthlyVacancyReserveDollars"
            @update:percent-of-rent="(v: number | null) => field.set('vacancyPercent', v)"
            @update:monthly-dollars="(v: number | null) => field.setNullable('monthlyVacancyReserveDollars', v)"
          />
          <PercentOfRentOrMonthlyDollarsInput
            data-testid="form.field.maintenancePercent"
            label="Maintenance"
            :percent-of-rent="field.get('maintenancePercent')"
            :monthly-dollars="field.getNullable('monthlyMaintenanceReserveDollars')"
            :monthly-rent-dollars="monthlyRentDollars"
            :info="impactText('maintenancePercent')"
            :percent-error-message="fieldErrorMessages?.maintenancePercent"
            :dollars-error-message="fieldErrorMessages?.monthlyMaintenanceReserveDollars"
            @update:percent-of-rent="(v: number | null) => field.set('maintenancePercent', v)"
            @update:monthly-dollars="(v: number | null) => field.setNullable('monthlyMaintenanceReserveDollars', v)"
          />
          <PercentOfRentOrMonthlyDollarsInput
            data-testid="form.field.capexPercent"
            label="CapEx"
            :percent-of-rent="field.get('capexPercent')"
            :monthly-dollars="field.getNullable('monthlyCapexReserveDollars')"
            :monthly-rent-dollars="monthlyRentDollars"
            :info="impactText('capexPercent')"
            :percent-error-message="fieldErrorMessages?.capexPercent"
            :dollars-error-message="fieldErrorMessages?.monthlyCapexReserveDollars"
            @update:percent-of-rent="(v: number | null) => field.set('capexPercent', v)"
            @update:monthly-dollars="(v: number | null) => field.setNullable('monthlyCapexReserveDollars', v)"
          />
          <PercentOfRentOrMonthlyDollarsInput
            data-testid="form.field.property_managment_fee_precentages_from_rent"
            label="Prop. Management"
            :percent-of-rent="field.get('property_managment_fee_precentages_from_rent')"
            :monthly-dollars="field.getNullable('monthlyPropertyManagementFeeDollars')"
            :monthly-rent-dollars="monthlyRentDollars"
            :info="impactText('property_managment_fee_precentages_from_rent')"
            :percent-error-message="fieldErrorMessages?.property_managment_fee_precentages_from_rent"
            :dollars-error-message="fieldErrorMessages?.monthlyPropertyManagementFeeDollars"
            @update:percent-of-rent="(v: number | null) => field.set('property_managment_fee_precentages_from_rent', v)"
            @update:monthly-dollars="(v: number | null) => field.setNullable('monthlyPropertyManagementFeeDollars', v)"
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
    </div>
    <template #footer>
      <AutoFigure data-testid="form.auto.preRefiRentalIncome" label="Pre-Refi Rental Income" :value="autoCalc.preRefiRentalIncome" :hint="preRefiRentHint" />
    </template>
  </LifecycleSection>
</template>
