<script setup lang="ts">
/**
 * The one and only deal-input form.
 *
 * Rendered by all three places a user types deal numbers:
 *   - `views/AnalyzeDeal.vue`   (new deal, `surface="card"`)
 *   - `views/MyDeals.vue`       (card detail modal, `surface="panel"`)
 *   - `views/BoughtDeals.vue`   (card detail modal, `surface="panel"`)
 *
 * ---------------------------------------------------------------------------
 * ADDING A NEW INPUT FIELD — the full checklist
 * ---------------------------------------------------------------------------
 * Frontend
 *  1. This file — add the <MoneyInput> / <NumberInput> / <SliderField> to the
 *     right section. Read with `get(...)`, write with `set(...)`.
 *  2. `types/index.ts` — add the field to `BaseDealReq` (shared by both deal
 *     types) or `BrrrAnalyzeReq` / `FlipAnalyzeReq` (type-specific).
 *     `DealInputModel`, `*DealCreate` and `AnalyzeDealReq` pick it up for free.
 *  3. `utils/dealUtils.ts` — add a default to `createEmptyDealForm`; if it's a
 *     BRRRR field with a *server* default, also add it to `BRRR_LEGACY_DEFAULTS`
 *     so `ensureBrrrLegacyDefaults` backfills rows saved before it existed; add
 *     a line to `formatDealForClipboard` if it belongs in the AI summary.
 *  4. `utils/dealUtils.ts` — add bounds checks to `validateDealInputs`.
 *
 * Backend
 *  5. `ReqRes/analyzeBRRR/analyzeBRRRReq.py` and/or
 *     `ReqRes/analyzeFlip/analyzeFlipReq.py`  (the /analyze/* endpoints), and
 *     `ReqRes/activeDeal/activeDealReq.py`    (BaseDealReq / *ActiveDealCreate).
 *     `ReqRes/boughtDeal/boughtDealReq.py` inherits — verify, don't duplicate.
 *     The Pydantic `alias=` MUST equal the field name used here.
 *  6. `ReqRes/analyzeBRRRRes.py` / `analyzeFlipRes.py` — only for computed
 *     *output* metrics, not raw inputs.
 *  7. `models.py` — add the Column to the `BaseDeal` mixin (shared) or to ALL
 *     FOUR of BrrrActiveDeal / FlipActiveDeal / BoughtBrrrDeal / BoughtFlipDeal.
 *  8. `main.py` `_run_migrations()` — call `_add_column_if_missing` for every
 *     affected existing table. The migration DEFAULT must match the model
 *     `default=` and the Pydantic default, because `update_*_deal` dumps every
 *     field (no `exclude_unset`) on each PUT.
 *  9. `main.py` — wire it into `calculate_brrr_results` / `calculate_flip_results`
 *     and `validate_*_inputs`; register a CalcStep if it feeds a headline metric.
 * 10. `crud_active_deal.py` / `crud_bought_deal.py` — no change expected (they
 *     iterate `__table__.columns` dynamically). Just confirm.
 * 11. `deal_pdf.py` — only if it's a headline metric.
 * 12. Extend `DealInputsForm.test.ts` and any backend calc test.
 *
 * ---------------------------------------------------------------------------
 * IMPORTANT: this component mutates `props.deal` IN PLACE.
 * ---------------------------------------------------------------------------
 * The card modals drive auto-save and re-analyze from a
 * `watch(editingDeal, ..., { deep: true })`. Replacing the object reference on
 * every keystroke would thrash that watcher and the `isDirty` / settle logic
 * around it, so we deliberately write through to the caller's object instead of
 * emitting a new one — exactly what the three inlined copies of this form did
 * before they were merged here.
 */
import MoneyInput from "./ui/MoneyInput.vue";
import NumberInput from "./ui/NumberInput.vue";
import SliderField from "./ui/SliderField.vue";
import ToggleSwitch from "primevue/toggleswitch";
import { computed } from "vue";
import type { DealInputModel } from "../types";
import {
  DEFAULT_CASH_RESERVE,
  DEFAULT_LONG_TERM_INTEREST_RATE,
  DEFAULT_LTV_PERCENT,
  DEFAULT_REFI_POINTS,
  toNumber,
} from "../utils/dealUtils";

defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    /** Mutated in place — see the note above. */
    deal: DealInputModel;
    dealType: "BRRRR" | "FLIP";
    /**
     * `card`  — white sections on a light page (Analyze page).
     * `panel` — grey sections inside a white modal (card detail modals).
     */
    surface?: "card" | "panel";
  }>(),
  { surface: "card" },
);

/** Keys on `DealInputModel` whose value is a number. Derived, so it stays in
 *  sync automatically when a numeric field is added to the request types. */
type NumericKey = {
  [K in keyof DealInputModel]-?: number extends NonNullable<DealInputModel[K]>
    ? K
    : never;
}[keyof DealInputModel];

/**
 * Read a numeric field for display. PrimeVue inputs expect `null` when empty.
 *
 * Goes through `toNumber` because a deal loaded from the API carries its money
 * and percentage fields as *strings* (`"200.00"` — FastAPI serialises `Decimal`
 * that way), while a deal the user is typing into carries real numbers. Checking
 * `typeof === "number"` here would blank out every saved deal's inputs.
 */
function get(key: NumericKey, fallback: number | null = null): number | null {
  return toNumber(props.deal[key]) ?? fallback;
}

/**
 * Write a numeric field back. Clearing an input stores `undefined`, not `0`, so
 * the field is omitted from the payload and the backend default applies.
 */
function set(key: NumericKey, value: number | null, fallback?: number): void {
  (props.deal as Record<NumericKey, number | undefined>)[key] =
    value ?? fallback;
}

const useHmForRehab = computed({
  get: () => props.deal.use_HM_for_rehab ?? false,
  set: (value: boolean) => {
    props.deal.use_HM_for_rehab = value;
  },
});

const isBrrr = computed(() => props.dealType === "BRRRR");

// Surface-dependent styling. The two variants are a straight inversion of each
// other: sections sit on white in the page, on grey inside the modals.
const sectionClass = computed(() =>
  props.surface === "panel"
    ? "bg-gray-50 p-6 rounded-2xl border border-gray-200 shadow-sm"
    : "bg-white p-6 rounded-2xl border border-gray-200 shadow-sm",
);
// The "Use HM for Rehab" box: grey-on-white in the page, white-on-grey in modals.
const innerBoxClass = computed(() =>
  props.surface === "panel"
    ? "bg-white border border-gray-200"
    : "bg-gray-50 border border-gray-200",
);
const quickButtonClass = computed(() =>
  props.surface === "panel"
    ? "bg-gray-50 border-gray-200 hover:bg-gray-100"
    : "bg-white border-gray-200 hover:bg-gray-50",
);
// Vertical gap between the sections. Previously supplied by the parent
// container (`space-y-8` on the Analyze page, `space-y-6` inside the modals);
// the component now owns it so those parents don't have to know the layout.
const rootSpacingClass = computed(() =>
  props.surface === "panel" ? "space-y-6" : "space-y-8",
);

// The two surfaces diverged on a few cosmetic details before the merge; these
// keep each host looking exactly as it did.
//
// Rehab Cost + Contingency: the modals pair them in a nested 2-col grid; the
// Analyze page laid them out as two normal grid cells. `contents` dissolves the
// wrapper so its children fall straight into the parent grid.
const rehabPairClass = computed(() =>
  props.surface === "panel" ? "grid grid-cols-2 gap-2" : "contents",
);
// Flip selling-costs box + heading.
const sellingBoxClass = computed(() =>
  props.surface === "panel"
    ? "bg-white border border-gray-200 mt-1"
    : "bg-gray-50 border border-gray-100",
);
const sellingBoxHeading = computed(() =>
  props.surface === "panel" ? "Selling Costs Breakdown" : "Selling Costs",
);

/** Populate the three selling-cost fields with the usual flip assumptions. */
const quickCalcSellingCosts = () => {
  props.deal.buyerAgentSellingFee = 3;
  props.deal.sellerAgentSellingFee = 3;
  props.deal.sellingClosingCosts = 5;
};
</script>

<template>
  <div :class="rootSpacingClass">
  <!-- Group 1: Buy & Rehab (shared by BRRRR + FLIP) -->
  <section :class="sectionClass">
    <h2
      class="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2"
    >
      <i class="pi pi-home text-blue-500"></i> Buy &amp; Rehab
    </h2>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <MoneyInput
        :model-value="get('purchasePrice')"
        @update:model-value="(v: number | null) => set('purchasePrice', v)"
        label="Purchase Price"
        :inThousands="true"
        :required="true"
      />
      <div :class="rehabPairClass">
        <MoneyInput
          :model-value="get('rehabCost')"
          @update:model-value="(v: number | null) => set('rehabCost', v)"
          label="Rehab Cost"
          :inThousands="true"
        />
        <NumberInput
          :model-value="get('rehabContingency')"
          @update:model-value="(v: number | null) => set('rehabContingency', v)"
          label="Contingency"
          suffix="%"
          :min="0"
          :max="100"
        />
      </div>
      <MoneyInput
        :model-value="get('closingCostsBuy')"
        @update:model-value="(v: number | null) => set('closingCostsBuy', v)"
        label="Closing Costs (Buy)"
        :inThousands="true"
      />

      <div class="md:col-span-2 border-t border-gray-200 my-2 pt-4">
        <h3 class="text-sm font-semibold text-gray-600 mb-3">
          Hard Money Details
        </h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <NumberInput
            :model-value="get('down_payment')"
            @update:model-value="(v: number | null) => set('down_payment', v)"
            label="Down Payment"
            suffix="%"
            :min="0"
            :max="100"
          />
          <NumberInput
            :model-value="get('hmlPoints')"
            @update:model-value="(v: number | null) => set('hmlPoints', v)"
            label="Points"
            suffix=" pts"
            :min="0"
            :max="100"
          />
          <NumberInput
            :model-value="get('HMLInterestRate')"
            @update:model-value="(v: number | null) => set('HMLInterestRate', v)"
            label="Interest Rate"
            suffix="%"
            :min="0"
            :max="100"
          />

          <div
            class="flex items-center justify-between p-3 rounded-lg"
            :class="innerBoxClass"
          >
            <span class="text-sm font-medium text-gray-700">
              Use HM for Rehab
            </span>
            <ToggleSwitch
              v-model="useHmForRehab"
              :pt="{
                slider: ({ props: sliderProps }: any) => ({
                  class: sliderProps.modelValue ? 'bg-blue-500' : 'bg-gray-400',
                }),
              }"
            />
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- Group 2a: Refinance (BRRRR only) -->
  <section v-if="isBrrr" :class="sectionClass">
    <h2
      class="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2"
    >
      <i class="pi pi-refresh text-blue-500"></i> Refinance (BRRRR)
    </h2>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <MoneyInput
        :model-value="get('arv_in_thousands')"
        @update:model-value="(v: number | null) => set('arv_in_thousands', v)"
        label="ARV"
        :inThousands="true"
        :required="true"
      />
      <SliderField
        :model-value="get('ltv_as_precent', DEFAULT_LTV_PERCENT)"
        @update:model-value="
          (v: number | null) => set('ltv_as_precent', v, DEFAULT_LTV_PERCENT)
        "
        label="LTV"
        :min="1"
        :max="100"
        suffix="%"
        :required="true"
      />

      <NumberInput
        :model-value="get('monthsUntilRefi')"
        @update:model-value="(v: number | null) => set('monthsUntilRefi', v)"
        label="Months until Refi"
        suffix=" mos"
      />
      <MoneyInput
        :model-value="get('closingCostsRefi')"
        @update:model-value="(v: number | null) => set('closingCostsRefi', v)"
        label="Refi Closing Costs"
        :inThousands="true"
      />
      <NumberInput
        :model-value="get('refiPoints', DEFAULT_REFI_POINTS)"
        @update:model-value="
          (v: number | null) => set('refiPoints', v, DEFAULT_REFI_POINTS)
        "
        label="Refi Points"
        suffix=" pts"
        :min="0"
        :max="100"
      />
      <MoneyInput
        :model-value="get('cashReserve', DEFAULT_CASH_RESERVE)"
        @update:model-value="
          (v: number | null) => set('cashReserve', v, DEFAULT_CASH_RESERVE)
        "
        label="Cash Reserve (paydown at refi)"
        :inThousands="true"
      />

      <SliderField
        :model-value="get('interestRate', DEFAULT_LONG_TERM_INTEREST_RATE)"
        @update:model-value="
          (v: number | null) =>
            set('interestRate', v, DEFAULT_LONG_TERM_INTEREST_RATE)
        "
        label="Long Term Interest Rate"
        :min="0"
        :max="20"
        :step="0.125"
        suffix="%"
        :required="true"
      />
      <NumberInput
        :model-value="get('loanTermYears')"
        @update:model-value="(v: number | null) => set('loanTermYears', v)"
        label="Loan Term"
        suffix=" Years"
      />
    </div>
  </section>

  <!-- Group 2b: Flip Strategy (FLIP only) -->
  <section v-else :class="sectionClass">
    <h2
      class="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2"
    >
      <i class="pi pi-dollar text-orange-500"></i> Flip Strategy
    </h2>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <MoneyInput
        :model-value="get('salePrice')"
        @update:model-value="(v: number | null) => set('salePrice', v)"
        label="Projected Sale Price"
        :inThousands="true"
        :required="true"
      />
      <NumberInput
        :model-value="get('holdingTime')"
        @update:model-value="(v: number | null) => set('holdingTime', v)"
        label="Holding Time"
        suffix=" mos"
        :required="true"
      />

      <div
        class="md:col-span-2 rounded-lg p-3"
        :class="sellingBoxClass"
      >
        <div class="flex justify-between items-center mb-3">
          <h3 class="text-sm font-semibold text-gray-700">
            {{ sellingBoxHeading }}
          </h3>
          <button
            type="button"
            @click="quickCalcSellingCosts"
            class="px-2 py-1 text-xs border rounded text-gray-600 transition-colors shadow-sm"
            :class="quickButtonClass"
          >
            Quick Defaults (3%/3%/$5k)
          </button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <NumberInput
            :model-value="get('buyerAgentSellingFee')"
            @update:model-value="
              (v: number | null) => set('buyerAgentSellingFee', v)
            "
            label="Buyer Agent Fee"
            suffix="%"
          />
          <NumberInput
            :model-value="get('sellerAgentSellingFee')"
            @update:model-value="
              (v: number | null) => set('sellerAgentSellingFee', v)
            "
            label="Seller Agent Fee"
            suffix="%"
          />
          <MoneyInput
            :model-value="get('sellingClosingCosts')"
            @update:model-value="
              (v: number | null) => set('sellingClosingCosts', v)
            "
            label="Closing Costs"
            :inThousands="true"
          />
        </div>
      </div>

      <NumberInput
        :model-value="get('capitalGainsTax')"
        @update:model-value="(v: number | null) => set('capitalGainsTax', v)"
        label="Capital Gains Tax Rate"
        suffix="%"
      />
    </div>
  </section>

  <!-- Group 3: Expenses (shared, with per-type extras) -->
  <section :class="sectionClass">
    <h2
      class="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2"
    >
      <i
        class="pi pi-wallet"
        :class="isBrrr ? 'text-blue-500' : 'text-orange-500'"
      ></i>
      Expenses
    </h2>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <MoneyInput
        v-if="isBrrr"
        :model-value="get('rent')"
        @update:model-value="(v: number | null) => set('rent', v)"
        label="Monthly Rent"
        :required="true"
      />

      <MoneyInput
        :model-value="get('annual_property_taxes')"
        @update:model-value="
          (v: number | null) => set('annual_property_taxes', v)
        "
        label="Annual Taxes"
      />
      <MoneyInput
        :model-value="get('annual_insurance')"
        @update:model-value="(v: number | null) => set('annual_insurance', v)"
        label="Annual Insurance"
      />
      <MoneyInput
        :model-value="get('montly_hoa')"
        @update:model-value="(v: number | null) => set('montly_hoa', v)"
        label="Monthly HOA"
      />
      <MoneyInput
        v-if="!isBrrr"
        :model-value="get('monthly_utilities')"
        @update:model-value="(v: number | null) => set('monthly_utilities', v)"
        label="Monthly Utilities"
      />

      <div
        v-if="isBrrr"
        class="md:col-span-2 grid grid-cols-2 md:grid-cols-4 gap-3 mt-2"
      >
        <NumberInput
          :model-value="get('vacancyPercent')"
          @update:model-value="(v: number | null) => set('vacancyPercent', v)"
          label="Vacancy"
          suffix="%"
        />
        <NumberInput
          :model-value="get('maintenancePercent')"
          @update:model-value="
            (v: number | null) => set('maintenancePercent', v)
          "
          label="Maint."
          suffix="%"
        />
        <NumberInput
          :model-value="get('capexPercent')"
          @update:model-value="(v: number | null) => set('capexPercent', v)"
          label="CapEx"
          suffix="%"
        />
        <NumberInput
          :model-value="get('property_managment_fee_precentages_from_rent')"
          @update:model-value="
            (v: number | null) =>
              set('property_managment_fee_precentages_from_rent', v)
          "
          label="Prop. Mgmt"
          suffix="%"
        />
      </div>
    </div>
  </section>
  </div>
</template>
