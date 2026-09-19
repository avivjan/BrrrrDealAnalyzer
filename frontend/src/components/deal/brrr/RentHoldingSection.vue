<script setup lang="ts">
/** BRRRR › Rent & Holding: the tenant, the pre-refi rent, and the carrying costs. */
import { computed } from "vue";
import type { DealInputModel } from "../../../types";
import { useDealField } from "../../../composables/useDealField";
import { brrrAutoCalc } from "../../../utils/brrrAutoCalc";
import { impactText } from "../../../config/brrrInputImpacts";
import { formatMoney } from "../../../utils/money";
import MoneyInput from "../../ui/MoneyInput.vue";
import NumberInput from "../../ui/NumberInput.vue";
import DaysOrDateField from "../../ui/DaysOrDateField.vue";
import LifecycleSection from "../LifecycleSection.vue";
import AutoFigure from "../AutoFigure.vue";

const props = defineProps<{ deal: DealInputModel; surface: "card" | "panel" }>();
const f = useDealField(props.deal);
const calc = computed(() => brrrAutoCalc(props.deal));

const rentHint = computed(() =>
  calc.value.daysRentedBeforeRefi == null ? undefined
    : calc.value.daysRentedBeforeRefi > 0 ? `${calc.value.daysRentedBeforeRefi} days rented before the refi` : "tenant placed at or after the refi",
);
</script>

<template>
  <LifecycleSection title="Rent & Holding" icon="pi-key" :surface="surface">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <MoneyInput
        data-testid="form.field.rent"
        :model-value="f.get('rent')"
        @update:model-value="(v: number | null) => f.set('rent', v)"
        label="Monthly Rent"
        :required="true"
        :info="impactText('rent')"
      />
      <DaysOrDateField
        data-testid="form.field.daysUntilRented"
        :model-value="f.get('daysUntilRented')"
        @update:model-value="(v: number | null) => f.set('daysUntilRented', v)"
        label="Until Tenant Occupied"
        date-label="Tenant occupied"
        :anchor-date="f.getStr('buyClosingDate')"
        :min="0"
        :info="impactText('daysUntilRented')"
      />
      <MoneyInput
        data-testid="form.field.monthlyUtilitiesUntilRented"
        :model-value="f.get('monthlyUtilitiesUntilRented')"
        @update:model-value="(v: number | null) => f.set('monthlyUtilitiesUntilRented', v)"
        label="Utilities until Rented (per month)"
        :info="impactText('monthlyUtilitiesUntilRented')"
        :note="calc.utilitiesUntilRented == null ? undefined : `= ${formatMoney(calc.utilitiesUntilRented)}`"
      />
      <MoneyInput
        data-testid="form.field.maintenanceBeforeRefi"
        :model-value="f.get('maintenanceBeforeRefi')"
        @update:model-value="(v: number | null) => f.set('maintenanceBeforeRefi', v)"
        label="Maintenance before Refi"
        :info="impactText('maintenanceBeforeRefi')"
      />
      <MoneyInput
        data-testid="form.field.appliances"
        :model-value="f.get('appliances')"
        @update:model-value="(v: number | null) => f.set('appliances', v)"
        label="Appliances"
        :info="impactText('appliances')"
      />
      <div class="hidden md:block"></div>

      <MoneyInput
        data-testid="form.field.annual_property_taxes"
        :model-value="f.get('annual_property_taxes')"
        @update:model-value="(v: number | null) => f.set('annual_property_taxes', v)"
        label="Annual Taxes"
        :info="impactText('annual_property_taxes')"
      />
      <MoneyInput
        data-testid="form.field.annual_insurance"
        :model-value="f.get('annual_insurance')"
        @update:model-value="(v: number | null) => f.set('annual_insurance', v)"
        label="Annual Insurance"
        :info="impactText('annual_insurance')"
      />
      <MoneyInput
        data-testid="form.field.montly_hoa"
        :model-value="f.get('montly_hoa')"
        @update:model-value="(v: number | null) => f.set('montly_hoa', v)"
        label="Monthly HOA"
        :info="impactText('montly_hoa')"
      />

      <div class="md:col-span-2 mt-2 grid grid-cols-2 gap-3 md:grid-cols-4">
        <NumberInput
          data-testid="form.field.vacancyPercent"
          :model-value="f.get('vacancyPercent')"
          @update:model-value="(v: number | null) => f.set('vacancyPercent', v)"
          label="Vacancy"
          suffix="%"
          :info="impactText('vacancyPercent')"
        />
        <NumberInput
          data-testid="form.field.maintenancePercent"
          :model-value="f.get('maintenancePercent')"
          @update:model-value="(v: number | null) => f.set('maintenancePercent', v)"
          label="Maint."
          suffix="%"
          :info="impactText('maintenancePercent')"
        />
        <NumberInput
          data-testid="form.field.capexPercent"
          :model-value="f.get('capexPercent')"
          @update:model-value="(v: number | null) => f.set('capexPercent', v)"
          label="CapEx"
          suffix="%"
          :info="impactText('capexPercent')"
        />
        <NumberInput
          data-testid="form.field.property_managment_fee_precentages_from_rent"
          :model-value="f.get('property_managment_fee_precentages_from_rent')"
          @update:model-value="(v: number | null) => f.set('property_managment_fee_precentages_from_rent', v)"
          label="Prop. Mgmt"
          suffix="%"
          :info="impactText('property_managment_fee_precentages_from_rent')"
        />
      </div>
    </div>
    <template #footer>
      <AutoFigure data-testid="form.auto.preRefiRentalIncome" label="Pre-Refi Rental Income" :value="calc.preRefiRentalIncome" :hint="rentHint" />
    </template>
  </LifecycleSection>
</template>
