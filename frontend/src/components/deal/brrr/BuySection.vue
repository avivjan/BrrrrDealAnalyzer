<script setup lang="ts">
/** BRRRR › Buy: the closing date, the hard-money stack and the purchase settlement. */
import { computed, useId } from "vue";
import type { DealInputModel, TitleModeBuy } from "../../../types";
import { useDealField } from "../../../composables/useDealField";
import { brrrAutoCalc } from "../../../utils/brrrAutoCalc";
import { impactText } from "../../../config/brrrInputImpacts";
import { formatMoney } from "../../../utils/money";
import MoneyInput from "../../ui/MoneyInput.vue";
import NumberInput from "../../ui/NumberInput.vue";
import AutoDefaultMoneyInput from "../../ui/AutoDefaultMoneyInput.vue";
import PresetSelectInput from "../../ui/PresetSelectInput.vue";
import InputInfo from "../../ui/InputInfo.vue";
import LifecycleSection from "../LifecycleSection.vue";
import AutoFigure from "../AutoFigure.vue";

const props = defineProps<{ deal: DealInputModel; surface: "card" | "panel" }>();
const f = useDealField(props.deal);
const calc = computed(() => brrrAutoCalc(props.deal));

const LOAN_CHARGE_PRESETS = [
  { label: "3shacks", value: 900 },
  { label: "212", value: 1900 },
];

const closingDateId = useId();
const titleModeId = useId();
const notaryId = useId();
const sellerPaidId = useId();

const onClosingDate = (event: Event) => {
  const value = (event.target as HTMLInputElement).value;
  f.setStr("buyClosingDate", value || null);
};
const onTitleMode = (event: Event) => {
  props.deal.titleModeBuy = (event.target as HTMLSelectElement).value as TitleModeBuy;
};

const sellerPaidExplicit = computed(() => typeof props.deal.sellerPaidCurrentYearTaxes === "boolean");
const sellerPaidChecked = computed(() => calc.value.sellerPaidCurrentYearTaxesEffective ?? false);

const money = (v: number | null) => (v == null ? undefined : `= ${formatMoney(v)}`);
const perDiem = computed(() => (calc.value.hmlPerDiem == null ? undefined : `${formatMoney(calc.value.hmlPerDiem)}/day`));
const prepaidHint = computed(() =>
  calc.value.prepaidDaysBuy != null ? `${calc.value.prepaidDaysBuy} days through month end` : undefined,
);
const taxHint = computed(() => {
  const paid = calc.value.sellerPaidCurrentYearTaxesEffective;
  if (paid == null) return undefined;
  return paid ? "buyer credits the seller (taxes already paid)" : "seller credits the buyer for the days owned";
});
</script>

<template>
  <LifecycleSection title="Buy" icon="pi-home" :surface="surface">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <!-- Closing date + the two figures it unlocks -->
      <div class="flex flex-col gap-1.5" data-testid="form.field.buyClosingDate">
        <div data-part="label-row" class="flex h-5 items-center gap-1">
          <label :for="closingDateId" data-part="label" class="text-sm font-medium leading-5 text-fg">Closing Date (Buy)</label>
          <InputInfo :content="impactText('buyClosingDate')" field-label="Closing Date (Buy)" />
        </div>
        <input :id="closingDateId" data-part="input" type="date" class="ui-input" :value="f.getStr('buyClosingDate') ?? ''" @change="onClosingDate" />
      </div>
      <div class="flex flex-col gap-2">
        <AutoFigure data-testid="form.auto.prepaidInterestBuy" label="Prepaid Interest (Buy)" :value="calc.prepaidInterestBuy" :hint="prepaidHint" />
        <AutoFigure data-testid="form.auto.sellerTaxCredit" label="Seller Tax Credit" :value="calc.sellerTaxCredit" :hint="taxHint" signed />
        <div v-if="calc.sellerPaidCurrentYearTaxesEffective != null" class="flex items-center gap-2 text-xs text-fg-muted" data-testid="form.field.sellerPaidCurrentYearTaxes">
          <input :id="sellerPaidId" type="checkbox" class="h-4 w-4 accent-primary" :checked="sellerPaidChecked"
                 @change="f.setBool('sellerPaidCurrentYearTaxes', ($event.target as HTMLInputElement).checked)" />
          <label :for="sellerPaidId">Seller already paid this year's taxes</label>
          <span v-if="!sellerPaidExplicit" data-part="auto" class="rounded-ctl bg-surface-3 px-1.5 text-[10px] uppercase tracking-wide">auto</span>
          <button v-else type="button" data-part="reset" class="text-primary hover:text-primary-hover" @click="f.setBool('sellerPaidCurrentYearTaxes', null)">auto</button>
          <InputInfo :content="impactText('sellerPaidCurrentYearTaxes')" field-label="Seller already paid this year's taxes" />
        </div>
      </div>

      <MoneyInput
        data-testid="form.field.purchasePrice"
        :model-value="f.get('purchasePrice')"
        @update:model-value="(v: number | null) => f.set('purchasePrice', v)"
        label="Purchase Price"
        :inThousands="true"
        :required="true"
        :info="impactText('purchasePrice')"
      />
      <MoneyInput
        data-testid="form.field.earnestMoneyDeposit"
        :model-value="f.get('earnestMoneyDeposit')"
        @update:model-value="(v: number | null) => f.set('earnestMoneyDeposit', v)"
        label="Earnest Money Deposit"
        :info="impactText('earnestMoneyDeposit')"
      />

      <!-- Hard money -->
      <div class="my-2 border-t border-line pt-4 md:col-span-2">
        <UiSectionHeader as="h4" class="mb-3">Hard Money</UiSectionHeader>
        <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
          <NumberInput
            data-testid="form.field.down_payment"
            :model-value="f.get('down_payment')"
            @update:model-value="(v: number | null) => f.set('down_payment', v)"
            label="Down Payment"
            suffix="%"
            :min="0"
            :max="100"
            :info="impactText('down_payment')"
            :note="calc.purchaseLoanAmount == null ? undefined : `loan ${formatMoney(calc.purchaseLoanAmount)}`"
          />
          <NumberInput
            data-testid="form.field.hmlPoints"
            :model-value="f.get('hmlPoints')"
            @update:model-value="(v: number | null) => f.set('hmlPoints', v)"
            label="Points"
            suffix=" pts"
            :min="0"
            :max="100"
            :info="impactText('hmlPoints')"
            :note="money(calc.hmlPointsDollars)"
          />
          <NumberInput
            data-testid="form.field.HMLInterestRate"
            :model-value="f.get('HMLInterestRate')"
            @update:model-value="(v: number | null) => f.set('HMLInterestRate', v)"
            label="Interest Rate"
            suffix="%"
            :min="0"
            :max="100"
            :info="impactText('HMLInterestRate')"
            :note="perDiem"
          />
        </div>
        <div class="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
          <AutoFigure data-testid="form.auto.hmlAmount" label="Total hard money loan" :value="calc.hmlAmount" hint="purchase loan + construction budget" />
          <AutoFigure data-testid="form.auto.totalHardMoneyCost" label="Total Hard Money Cost" :value="calc.totalHardMoneyCost" hint="points + interest until refi + loan charges" />
        </div>
      </div>

      <!-- Closing costs (buy) -->
      <div class="my-2 border-t border-line pt-4 md:col-span-2">
        <UiSectionHeader as="h4" class="mb-3">Closing Costs (Buy)</UiSectionHeader>
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <PresetSelectInput
            data-testid="form.field.loanChargesBuy"
            :model-value="f.get('loanChargesBuy')"
            @update:model-value="(v: number | null) => f.set('loanChargesBuy', v)"
            label="Loan Charges"
            :presets="LOAN_CHARGE_PRESETS"
            :info="impactText('loanChargesBuy')"
          />
          <AutoDefaultMoneyInput
            data-testid="form.field.recordingTransferBuy"
            :model-value="f.getNullable('recordingTransferBuy')"
            :computed-default="calc.recordingTransferBuyDefault"
            @update:model-value="(v: number | null) => f.setNullable('recordingTransferBuy', v)"
            label="Recording & Transfer"
            :info="impactText('recordingTransferBuy')"
          />
          <div class="flex flex-col gap-1.5" data-testid="form.field.titleModeBuy">
            <div data-part="label-row" class="flex h-5 items-center gap-1">
              <label :for="titleModeId" data-part="label" class="text-sm font-medium leading-5 text-fg">Title Charges</label>
              <InputInfo :content="impactText('titleModeBuy')" field-label="Title Charges" />
            </div>
            <select :id="titleModeId" data-part="select" class="ui-select" :value="deal.titleModeBuy ?? 'standard'" @change="onTitleMode">
              <option value="standard">Standard (lender's policy)</option>
              <option value="we_pay_all">We pay all closing costs</option>
            </select>
          </div>
          <AutoDefaultMoneyInput
            data-testid="form.field.titleEscrowBuy"
            :model-value="f.getNullable('titleEscrowBuy')"
            :computed-default="calc.titleEscrowBuyDefault"
            @update:model-value="(v: number | null) => f.setNullable('titleEscrowBuy', v)"
            label="Title & Escrow / Settlement"
            :info="impactText('titleEscrowBuy')"
          />
          <div class="flex items-center gap-2 rounded-ctl border-ui border-line p-3 group-data-[surface=card]:bg-surface-2 group-data-[surface=panel]:bg-surface" data-testid="form.field.onlineNotaryBuy">
            <input :id="notaryId" type="checkbox" class="h-4 w-4 accent-primary" :checked="f.getBool('onlineNotaryBuy', true)"
                   @change="f.setBool('onlineNotaryBuy', ($event.target as HTMLInputElement).checked)" />
            <label :for="notaryId" class="text-sm font-medium text-fg">Online notary (+$250)</label>
            <InputInfo :content="impactText('onlineNotaryBuy')" field-label="Online notary" />
          </div>
          <MoneyInput
            data-testid="form.field.otherClosingCostsBuy"
            :model-value="f.get('otherClosingCostsBuy')"
            @update:model-value="(v: number | null) => f.set('otherClosingCostsBuy', v)"
            label="Other Closing Costs"
            :info="impactText('otherClosingCostsBuy')"
          />
        </div>
        <div class="mt-3">
          <AutoFigure data-testid="form.auto.closingCostsBuyTotal" label="Total closing costs (Buy)" :value="calc.closingCostsBuyTotal" />
        </div>
      </div>
    </div>
    <template #footer>
      <AutoFigure data-testid="form.auto.cashToCloseBuy" label="Cash to Close (Buy)" :value="calc.cashToCloseBuy" hint="down payment + closing costs + points + prepaid interest − tax credit − EMD" />
    </template>
  </LifecycleSection>
</template>
