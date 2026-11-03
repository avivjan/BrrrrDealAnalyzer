<script setup lang="ts">
/**
 * BRRRR › Buy: the contract and closing dates, the hard-money stack and the purchase settlement,
 * with the insurance bill at purchase (a line of that settlement when paid inside it).
 */
import { computed, useId } from "vue";
import type { DealInputModel, InsurancePurchaseBillPaymentTiming, TitleModeBuy } from "../../../types";
import { useDealField, type DealInputFieldKey } from "../../../composables/useDealField";
import { addDays, annualPropertyTaxesFromSellerTaxCredit, brrrAutoCalc, parseIsoDate } from "../../../utils/brrrAutoCalc";
import { DEFAULT_DAYS_FROM_CONTRACT_TO_BUY_CLOSING } from "../../../utils/dealUtils";
import { recordingTransferBuyEstimateExplanationLines, titleEscrowBuyEstimateExplanationLines } from "../../../utils/closingCostEstimateExplanations";
import { impactText } from "../../../config/brrrInputImpacts";
import { formatMoney } from "../../../utils/money";
import MoneyInput from "../../ui/MoneyInput.vue";
import NumberInput from "../../ui/NumberInput.vue";
import AutoDefaultMoneyInput from "../../ui/AutoDefaultMoneyInput.vue";
import PresetSelectInput from "../../ui/PresetSelectInput.vue";
import InputInfo from "../../ui/InputInfo.vue";
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

const LOAN_CHARGE_PRESETS = [
  { label: "3shacks", value: 900 },
  { label: "212", value: 1900 },
];

const contractDateId = useId();
const contractDateErrorId = useId();
const closingDateId = useId();
const closingDateErrorId = useId();
const titleModeId = useId();
const notaryId = useId();
const otherClosingCostsNoteId = useId();
const NOTARY_FEE_DEFAULT = 250;
const sellerPaidId = useId();
const insurancePurchaseBillPaymentTimingId = useId();

/**
 * The closing date follows the contract date (contract + 10 days) while it is still that default
 * or empty; once a closing date is typed by hand it stays where it was put.
 */
const closingDateIsStillTheDefaultForContractDate = (previousContractDate: string | null): boolean => {
  const currentClosingDate = field.getStr("buyClosingDate");
  if (!currentClosingDate) return true;
  return previousContractDate != null && currentClosingDate === addDays(previousContractDate, DEFAULT_DAYS_FROM_CONTRACT_TO_BUY_CLOSING);
};
const onContractDate = (event: Event) => {
  const newContractDate = (event.target as HTMLInputElement).value || null;
  const closingDateFollowsTheContractDate = closingDateIsStillTheDefaultForContractDate(field.getStr("contractDate"));
  field.setStr("contractDate", newContractDate);
  if (newContractDate && closingDateFollowsTheContractDate) {
    field.setStr("buyClosingDate", addDays(newContractDate, DEFAULT_DAYS_FROM_CONTRACT_TO_BUY_CLOSING));
  }
};
const onClosingDate = (event: Event) => {
  const value = (event.target as HTMLInputElement).value;
  field.setStr("buyClosingDate", value || null);
};
const onTitleMode = (event: Event) => {
  props.deal.titleModeBuy = (event.target as HTMLSelectElement).value as TitleModeBuy;
};
const onInsurancePurchaseBillPaymentTiming = (event: Event) => {
  props.deal.insurancePurchaseBillPaymentTiming = (event.target as HTMLSelectElement).value as InsurancePurchaseBillPaymentTiming;
};
const titleEscrowBuyExplanationLines = computed(() => titleEscrowBuyEstimateExplanationLines(autoCalc.value.titleEscrowBuyItemizedDefault));
const recordingTransferBuyExplanationLines = computed(() =>
  recordingTransferBuyEstimateExplanationLines(autoCalc.value.hmlAmount, autoCalc.value.deedTransferTaxBuy, autoCalc.value.recordingTransferBuyDefault),
);

/**
 * Who pays this year's tax bill, one choice stored in two fields: `sellerPaidCurrentYearTaxes`
 * (null = auto by the closing month) and `buyerPaysCurrentYearTaxBillAtPurchaseClosing`.
 */
type CurrentYearPropertyTaxBillChoice = "seller_paid_or_pays_at_closing" | "we_pay_at_purchase_closing" | "we_pay_in_november_outside_closing";
const CURRENT_YEAR_PROPERTY_TAX_BILL_CHOICES: { value: CurrentYearPropertyTaxBillChoice; label: string }[] = [
  { value: "seller_paid_or_pays_at_closing", label: "Seller already paid / pays it at closing (we reimburse our days)" },
  { value: "we_pay_at_purchase_closing", label: "We pay it at closing (seller credits their days)" },
  { value: "we_pay_in_november_outside_closing", label: "We pay it in November, outside closing (POC)" },
];
const currentYearPropertyTaxBillChoiceIsAuto = computed(() =>
  props.deal.buyerPaysCurrentYearTaxBillAtPurchaseClosing !== true && typeof props.deal.sellerPaidCurrentYearTaxes !== "boolean");
const currentYearPropertyTaxBillChoice = computed<CurrentYearPropertyTaxBillChoice>(() => {
  if (props.deal.buyerPaysCurrentYearTaxBillAtPurchaseClosing === true) return "we_pay_at_purchase_closing";
  return autoCalc.value.sellerPaidCurrentYearTaxesEffective ? "seller_paid_or_pays_at_closing" : "we_pay_in_november_outside_closing";
});
const onCurrentYearPropertyTaxBillChoice = (event: Event) => {
  const choice = (event.target as HTMLSelectElement).value as CurrentYearPropertyTaxBillChoice;
  props.deal.buyerPaysCurrentYearTaxBillAtPurchaseClosing = choice === "we_pay_at_purchase_closing";
  field.setBool("sellerPaidCurrentYearTaxes", choice === "seller_paid_or_pays_at_closing" ? true : choice === "we_pay_in_november_outside_closing" ? false : null);
};
const closingCostsBuyTotalHint = computed(() => {
  const includedBills = [
    autoCalc.value.insuranceBillAtPurchaseInsideClosing ? `the insurance bill ${formatMoney(autoCalc.value.insuranceBillAtPurchaseInsideClosing)}` : null,
    autoCalc.value.propertyTaxBillPaidAtPurchaseClosing ? `this year's tax bill ${formatMoney(autoCalc.value.propertyTaxBillPaidAtPurchaseClosing)}` : null,
  ].filter(Boolean);
  return includedBills.length ? `includes ${includedBills.join(" and ")}` : undefined;
});
const resetCurrentYearPropertyTaxBillChoiceToAuto = () => {
  props.deal.buyerPaysCurrentYearTaxBillAtPurchaseClosing = false;
  field.setBool("sellerPaidCurrentYearTaxes", null);
};
const currentYearPropertyTaxBillHint = computed(() => {
  if (currentYearPropertyTaxBillChoice.value === "we_pay_at_purchase_closing") {
    const billAtClosing = autoCalc.value.propertyTaxBillPaidAtPurchaseClosing;
    return `the whole bill is a closing line: ${formatMoney(billAtClosing)} (−4% in Nov, −3% in Dec, else full)`;
  }
  return currentYearPropertyTaxBillChoice.value === "seller_paid_or_pays_at_closing"
    ? "the tax bucket starts saving for next year's bill"
    : "the seller's credit goes into the tax bucket, which pays the bill on Nov 30 (−4%)";
});

/** The lender finances price + fee; the deed tax and the owner's title policy stay on the contract price. */
const assignmentFeeNote = computed(() =>
  autoCalc.value.purchasePriceWithAssignmentFee != null && numberOrZeroForNote(props.deal.assignmentFee) > 0
    ? `financed: ${formatMoney(autoCalc.value.purchasePriceWithAssignmentFee)} total`
    : undefined,
);
const numberOrZeroForNote = (value: unknown) => Number(value) || 0;
const moneyNote = (amount: number | null) => (amount == null ? undefined : `= ${formatMoney(amount)}`);
const perDiemNote = computed(() => (autoCalc.value.hmlPerDiem == null ? undefined : `${formatMoney(autoCalc.value.hmlPerDiem)}/day`));
const prepaidInterestHint = computed(() =>
  autoCalc.value.prepaidDaysBuy != null ? `${autoCalc.value.prepaidDaysBuy} days through month end` : undefined,
);
const sellerTaxCreditHint = computed(() => {
  const paid = autoCalc.value.sellerPaidCurrentYearTaxesEffective;
  const proratedDays = autoCalc.value.sellerTaxCreditProratedDays;
  if (paid == null || proratedDays == null) return undefined;
  if (proratedDays === 0) return "no seller days before a Jan 1 closing, nothing to prorate";
  if (paid) return `buyer credits the seller for ${proratedDays} days (taxes already paid) · a real cost`;
  return props.deal.buyerPaysCurrentYearTaxBillAtPurchaseClosing === true
    ? `seller credits the buyer for ${proratedDays} days owned · against the bill we pay at closing`
    : `seller credits the buyer for ${proratedDays} days owned · set aside for the tax bill after closing`;
});
/** The pencil only makes sense while the proration covers at least one day (a Jan 1 unpaid closing has no seller days). */
const sellerTaxCreditIsEditable = computed(() => (autoCalc.value.sellerTaxCreditProratedDays ?? 0) > 0);
const sellerTaxCreditIsTyped = computed(() => props.deal.sellerTaxCreditAtPurchaseClosing != null);
/**
 * The credit typed over the figure is the one on the settlement statement (the county-tax and
 * assessment lines together). It overrides the proration, and this year's tax bill follows it:
 * the bill becomes the one whose proration gives that credit (both Property Tax Bill boxes
 * update). The direction comes from "seller already paid", so a December reimbursement reads
 * negative whatever sign it is typed with.
 */
const onSellerTaxCreditEdited = (sellerTaxCreditDollars: number) => {
  const sellerAlreadyPaid = autoCalc.value.sellerPaidCurrentYearTaxesEffective;
  const typedAmount = Math.abs(sellerTaxCreditDollars);
  field.setNullable("sellerTaxCreditAtPurchaseClosing", sellerAlreadyPaid ? -typedAmount : typedAmount);
  const buyClosingDay = parseIsoDate(field.getStr("buyClosingDate"));
  if (buyClosingDay == null || sellerAlreadyPaid == null) return;
  const propertyTaxBillGivingThatCredit = annualPropertyTaxesFromSellerTaxCredit(typedAmount, buyClosingDay, sellerAlreadyPaid);
  if (propertyTaxBillGivingThatCredit != null) field.set("annual_property_taxes", propertyTaxBillGivingThatCredit);
};
</script>

<template>
  <LifecycleSection title="Buy" icon="pi-home" :surface="surface">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <!-- The two mandatory dates; the closing date unlocks the two figures beside them -->
      <div class="flex flex-col gap-4">
        <div class="flex flex-col gap-1.5" data-testid="form.field.contractDate">
          <div data-part="label-row" class="flex h-5 items-center gap-1">
            <label :for="contractDateId" data-part="label" class="text-sm font-medium leading-5 text-fg">Contract Date</label>
            <InputInfo :content="impactText('contractDate')" field-label="Contract Date" />
          </div>
          <input
            :id="contractDateId"
            v-shake="fieldErrorMessages?.contractDate"
            data-part="input"
            type="date"
            required
            class="ui-input"
            :class="fieldErrorMessages?.contractDate ? 'ui-input-invalid' : ''"
            :aria-invalid="fieldErrorMessages?.contractDate ? 'true' : undefined"
            :aria-describedby="fieldErrorMessages?.contractDate ? contractDateErrorId : undefined"
            :value="field.getStr('contractDate') ?? ''"
            @change="onContractDate"
          />
          <p v-if="fieldErrorMessages?.contractDate" :id="contractDateErrorId" role="alert" data-part="error-message" class="text-xs text-negative">{{ fieldErrorMessages.contractDate }}</p>
        </div>
        <div class="flex flex-col gap-1.5" data-testid="form.field.buyClosingDate">
          <div data-part="label-row" class="flex h-5 items-center gap-1">
            <label :for="closingDateId" data-part="label" class="text-sm font-medium leading-5 text-fg">Closing Date (Buy)</label>
            <InputInfo :content="impactText('buyClosingDate')" field-label="Closing Date (Buy)" />
          </div>
          <input
            :id="closingDateId"
            v-shake="fieldErrorMessages?.buyClosingDate"
            data-part="input"
            type="date"
            required
            class="ui-input"
            :class="fieldErrorMessages?.buyClosingDate ? 'ui-input-invalid' : ''"
            :aria-invalid="fieldErrorMessages?.buyClosingDate ? 'true' : undefined"
            :aria-describedby="fieldErrorMessages?.buyClosingDate ? closingDateErrorId : undefined"
            :value="field.getStr('buyClosingDate') ?? ''"
            @change="onClosingDate"
          />
          <p v-if="fieldErrorMessages?.buyClosingDate" :id="closingDateErrorId" role="alert" data-part="error-message" class="text-xs text-negative">{{ fieldErrorMessages.buyClosingDate }}</p>
        </div>
      </div>
      <div class="flex flex-col gap-2">
        <AutoFigure data-testid="form.auto.prepaidInterestBuy" label="Prepaid Interest (Buy)" :value="autoCalc.prepaidInterestBuy" :hint="prepaidInterestHint" />
        <AutoFigure
          data-testid="form.auto.sellerTaxCredit"
          label="Seller Tax Credit"
          :value="autoCalc.sellerTaxCredit"
          :hint="sellerTaxCreditIsTyped ? 'as on the settlement statement' : sellerTaxCreditHint"
          signed
          :editable="sellerTaxCreditIsEditable"
          edit-aria-label="Type the seller tax credit on the settlement statement"
          @commit-edited-value="onSellerTaxCreditEdited"
        />
        <div v-if="sellerTaxCreditIsTyped" class="flex items-center gap-2 text-xs text-fg-muted" data-testid="form.field.sellerTaxCreditAtPurchaseClosing">
          <span>Typed from the settlement statement<template v-if="autoCalc.sellerTaxCreditFormula != null">; the proration gives {{ formatMoney(autoCalc.sellerTaxCreditFormula) }}</template></span>
          <button type="button" data-part="reset" class="text-primary hover:text-primary-hover" @click="field.setNullable('sellerTaxCreditAtPurchaseClosing', null)">auto</button>
          <InputInfo :content="impactText('sellerTaxCreditAtPurchaseClosing')" field-label="Seller Tax Credit" />
        </div>
        <!-- The same field as Rent & Holding's tax bill, shown here so the credit and the bill behind it are read together. -->
        <MoneyInput
          data-testid="form.field.annualPropertyTaxesBuyClone"
          :error-message="fieldErrorMessages?.annual_property_taxes"
          :model-value="field.get('annual_property_taxes')"
          @update:model-value="(v: number | null) => field.set('annual_property_taxes', v)"
          label="Property Tax Bill (this year)"
          note="same field as Rent & Holding"
          :info="impactText('annual_property_taxes')"
        />
        <div v-if="autoCalc.sellerPaidCurrentYearTaxesEffective != null" class="flex flex-col gap-1.5" data-testid="form.field.sellerPaidCurrentYearTaxes">
          <div data-part="label-row" class="flex h-5 items-center justify-between gap-1">
            <span class="inline-flex items-center gap-1">
              <label :for="sellerPaidId" data-part="label" class="text-sm font-medium leading-5 text-fg">This year's tax bill</label>
              <InputInfo :content="impactText('sellerPaidCurrentYearTaxes')" field-label="This year's tax bill" />
            </span>
            <span v-if="currentYearPropertyTaxBillChoiceIsAuto" data-part="auto" class="rounded-ctl bg-surface-3 px-1.5 text-[10px] font-medium uppercase tracking-wide text-fg-muted">auto</span>
            <button v-else type="button" data-part="reset" class="text-xs font-medium text-primary hover:text-primary-hover" @click="resetCurrentYearPropertyTaxBillChoiceToAuto">auto</button>
          </div>
          <select :id="sellerPaidId" data-part="select" class="ui-select" :value="currentYearPropertyTaxBillChoice" @change="onCurrentYearPropertyTaxBillChoice">
            <option v-for="choice in CURRENT_YEAR_PROPERTY_TAX_BILL_CHOICES" :key="choice.value" :value="choice.value">{{ choice.label }}</option>
          </select>
          <p data-part="hint" class="numeric text-xs text-fg-muted">{{ currentYearPropertyTaxBillHint }}</p>
        </div>
      </div>

      <MoneyInput
        data-testid="form.field.purchasePrice"
        :error-message="fieldErrorMessages?.purchasePrice"
        :model-value="field.get('purchasePrice')"
        @update:model-value="(v: number | null) => field.set('purchasePrice', v)"
        label="Purchase Price"
        :inThousands="true"
        :required="true"
        :needed-to-run-analysis="true"
        :info="impactText('purchasePrice')"
      />
      <MoneyInput
        data-testid="form.field.assignmentFee"
        :error-message="fieldErrorMessages?.assignmentFee"
        :model-value="field.get('assignmentFee')"
        @update:model-value="(v: number | null) => field.set('assignmentFee', v)"
        label="Assignment Fee"
        :note="assignmentFeeNote"
        :info="impactText('assignmentFee')"
      />
      <MoneyInput
        data-testid="form.field.earnestMoneyDeposit"
        :error-message="fieldErrorMessages?.earnestMoneyDeposit"
        :model-value="field.get('earnestMoneyDeposit')"
        @update:model-value="(v: number | null) => field.set('earnestMoneyDeposit', v)"
        label="Earnest Money Deposit"
        :info="impactText('earnestMoneyDeposit')"
      />

      <!-- Hard money -->
      <div class="my-2 border-t border-line pt-4 md:col-span-2">
        <UiSectionHeader as="h4" class="mb-3">Hard Money</UiSectionHeader>
        <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
          <NumberInput
            data-testid="form.field.down_payment"
            :error-message="fieldErrorMessages?.down_payment"
            :model-value="field.get('down_payment')"
            @update:model-value="(v: number | null) => field.set('down_payment', v)"
            label="Down Payment"
            suffix="%"
            :info="impactText('down_payment')"
            :note="autoCalc.purchaseLoanAmount == null ? undefined : `loan ${formatMoney(autoCalc.purchaseLoanAmount)}`"
          />
          <NumberInput
            data-testid="form.field.hmlPoints"
            :error-message="fieldErrorMessages?.hmlPoints"
            :model-value="field.get('hmlPoints')"
            @update:model-value="(v: number | null) => field.set('hmlPoints', v)"
            label="Points"
            suffix=" pts"
            :info="impactText('hmlPoints')"
            :note="moneyNote(autoCalc.hmlPointsDollars)"
          />
          <NumberInput
            data-testid="form.field.HMLInterestRate"
            :error-message="fieldErrorMessages?.HMLInterestRate"
            :model-value="field.get('HMLInterestRate')"
            @update:model-value="(v: number | null) => field.set('HMLInterestRate', v)"
            label="Interest Rate"
            suffix="%"
            :info="impactText('HMLInterestRate')"
            :note="perDiemNote"
          />
        </div>
        <div class="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
          <AutoFigure data-testid="form.auto.hmlAmount" label="Total hard money loan" :value="autoCalc.hmlAmount" hint="purchase loan + construction budget" />
          <AutoFigure data-testid="form.auto.totalHardMoneyCost" label="Total Hard Money Cost" :value="autoCalc.totalHardMoneyCost" hint="points + interest until refi + loan charges" />
        </div>
      </div>

      <!-- Closing costs (buy) -->
      <div class="my-2 border-t border-line pt-4 md:col-span-2">
        <UiSectionHeader as="h4" class="mb-3">Closing Costs (Buy)</UiSectionHeader>
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <PresetSelectInput
            data-testid="form.field.loanChargesBuy"
            :error-message="fieldErrorMessages?.loanChargesBuy"
            :model-value="field.get('loanChargesBuy')"
            @update:model-value="(v: number | null) => field.set('loanChargesBuy', v)"
            label="Loan Charges"
            :presets="LOAN_CHARGE_PRESETS"
            :info="impactText('loanChargesBuy')"
          />
          <AutoDefaultMoneyInput
            data-testid="form.field.recordingTransferBuy"
            :error-message="fieldErrorMessages?.recordingTransferBuy"
            :model-value="field.getNullable('recordingTransferBuy')"
            :computed-default="autoCalc.recordingTransferBuyDefault"
            @update:model-value="(v: number | null) => field.setNullable('recordingTransferBuy', v)"
            label="Recording & Transfer"
            :info="impactText('recordingTransferBuy')"
            :estimate-explanation-lines="recordingTransferBuyExplanationLines"
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
            <p v-if="autoCalc.wePayAllExtraClosingCost != null" data-testid="form.auto.wePayAllExtraClosingCost" class="numeric text-xs text-fg-muted">
              Paying all closing costs adds <span class="font-semibold text-fg">{{ formatMoney(autoCalc.wePayAllExtraClosingCost) }}</span> over standard
              <span class="text-fg-muted">(owner's title policy + 0.70% deed transfer tax)</span>
            </p>
          </div>
          <AutoDefaultMoneyInput
            data-testid="form.field.titleEscrowBuy"
            :error-message="fieldErrorMessages?.titleEscrowBuy"
            :model-value="field.getNullable('titleEscrowBuy')"
            :computed-default="autoCalc.titleEscrowBuyDefault"
            @update:model-value="(v: number | null) => field.setNullable('titleEscrowBuy', v)"
            label="Title & Escrow / Settlement"
            :info="impactText('titleEscrowBuy')"
            :estimate-explanation-lines="titleEscrowBuyExplanationLines"
          />
          <div class="flex flex-col gap-2 rounded-ctl border-ui border-line p-3 group-data-[surface=card]:bg-surface-2 group-data-[surface=panel]:bg-surface" data-testid="form.field.onlineNotaryBuy">
            <div class="flex items-center gap-2">
              <input :id="notaryId" type="checkbox" class="h-4 w-4 accent-primary" :checked="field.getBool('onlineNotaryBuy', true)"
                     @change="field.setBool('onlineNotaryBuy', ($event.target as HTMLInputElement).checked)" />
              <label :for="notaryId" class="text-sm font-medium text-fg">Online notary</label>
              <InputInfo :content="impactText('onlineNotaryBuy')" field-label="Online notary" />
            </div>
            <AutoDefaultMoneyInput
              v-if="field.getBool('onlineNotaryBuy', true)"
              data-testid="form.field.onlineNotaryFeeBuy"
              :error-message="fieldErrorMessages?.onlineNotaryFeeBuy"
              :model-value="field.getNullable('onlineNotaryFeeBuy')"
              :computed-default="NOTARY_FEE_DEFAULT"
              @update:model-value="(v: number | null) => field.setNullable('onlineNotaryFeeBuy', v)"
              label="Notary fee"
              :info="impactText('onlineNotaryFeeBuy')"
            />
          </div>
          <div class="flex flex-col gap-1.5">
            <MoneyInput
              data-testid="form.field.otherClosingCostsBuy"
              :error-message="fieldErrorMessages?.otherClosingCostsBuy"
              :model-value="field.get('otherClosingCostsBuy')"
              @update:model-value="(v: number | null) => field.set('otherClosingCostsBuy', v)"
              label="Other Closing Costs"
              :info="impactText('otherClosingCostsBuy')"
            />
            <input
              :id="otherClosingCostsNoteId"
              data-testid="form.field.otherClosingCostsBuyNote"
              type="text"
              maxlength="500"
              class="ui-input text-xs"
              placeholder="What is it for? (HOA transfer, warranty…)"
              aria-label="What the other closing costs are for"
              :value="field.getStr('otherClosingCostsBuyNote') ?? ''"
              @change="field.setStr('otherClosingCostsBuyNote', ($event.target as HTMLInputElement).value || null)"
            />
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
        </div>
        <div class="mt-3">
          <AutoFigure data-testid="form.auto.closingCostsBuyTotal" label="Total closing costs (Buy)" :value="autoCalc.closingCostsBuyTotal"
                      :hint="closingCostsBuyTotalHint" />
        </div>
      </div>
    </div>
    <template #footer>
      <AutoFigure data-testid="form.auto.cashToCloseBuy" label="Cash to Close (Buy)" :value="autoCalc.cashToCloseBuy" hint="down payment + closing costs + points + prepaid interest − tax credit − EMD" />
    </template>
  </LifecycleSection>
</template>
