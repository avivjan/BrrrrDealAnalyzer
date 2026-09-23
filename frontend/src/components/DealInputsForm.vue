<script setup lang="ts">
/**
 * The one and only deal-input form.
 *
 * Rendered by all three places a user types deal numbers:
 *   - `views/AnalyzeDeal.vue`   (new deal, `surface="card"`)
 *   - `views/MyDeals.vue`       (card detail modal, `surface="panel"`)
 *   - `views/BoughtDeals.vue`   (card detail modal, `surface="panel"`)
 *
 * The phases are TABS (Buy / Rehab / Rent & Holding / Refinance; Buy & Rehab /
 * Flip Strategy / Expenses), one section on screen at a time: the whole form
 * was one long scroll inside the card modals. Every section stays mounted and
 * switches with `v-show`, so a section's own state (the rehab mirror-once), the
 * unit tests that find any field, and the e2e locators all keep working; the
 * hosts' results panel sits below this component, outside the tabs, so it is
 * visible whatever tab is open. A tab carries a dot while one of its
 * `neededToRunAnalysis` inputs is still empty, so a first-time user sees where
 * to type to get a first result.
 *
 * ---------------------------------------------------------------------------
 * ADDING A NEW INPUT FIELD — the full checklist
 * ---------------------------------------------------------------------------
 * Frontend
 *  1. BRRRR: the lifecycle section that owns the input, under
 *     `components/deal/brrr/` (Buy, Rehab, RentHolding, Refinance). Read with
 *     `f.get(...)`, write with `f.set(...)` (`useDealField`); a "null = formula
 *     default" field uses `AutoDefaultMoneyInput` + `f.getNullable/setNullable`.
 *     Give it `:info="impactText('<field>')"` and add the field to
 *     `config/brrrInputImpacts.ts`; an inline figure goes in `utils/brrrAutoCalc.ts`.
 *     FLIP: this file. Money fields stored in thousands pass `:inThousands`.
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
 *  5. BRRRR lifecycle input: `ReqRes/common/brrr_lifecycle_inputs.py` (one
 *     declaration, inherited by the calculator request and the saved-deal
 *     models). Shared or FLIP input: `ReqRes/common/analyze_inputs.py` and
 *     `ReqRes/common/base_deal.py` / `active_deal_schemas.py`.
 *     The Pydantic `alias=` MUST equal the field name used here.
 *  6. `ReqRes/common/analyze_results.py` — only for computed *output* metrics.
 *  7. `DAL/data_models/common/brrr_lifecycle.py` (BRRRR, both tables at once),
 *     `common/base_deal.py` (shared) or the Flip classes in `activeDeal/` +
 *     `boughtDeal/deals.py`.
 *  8. `migrations/steps/brrr_lifecycle_columns.py` (BRRRR) or
 *     `migrations/runner.py`. The DDL DEFAULT must match the model `default=`
 *     and the Pydantic default, because `update_*_deal` dumps every field on PUT.
 *  9. `BL/analyze/brrrSteps/` — use it in the step that owns the subject, add
 *     any intermediate to `brrr_results_with_intermediates.py`, explain it in
 *     `BL/analyze/explain/brrr.py`, bound it in `BL/analyze/common/validation.py`.
 * 10. `DAL/crud/` — no change expected (they iterate `__table__.columns`).
 * 11. `BRRR_SECTIONS` in `explain/brrr.py` — only if it's a headline metric.
 * 12. Extend `DealInputsForm.test.ts`, `brrrAutoCalc.test.ts`,
 *     `tests/test_brrr_lifecycle.py`; re-record the backend goldens.
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
import BuySection from "./deal/brrr/BuySection.vue";
import RehabSection from "./deal/brrr/RehabSection.vue";
import RentHoldingSection from "./deal/brrr/RentHoldingSection.vue";
import RefinanceSection from "./deal/brrr/RefinanceSection.vue";
import MoneyInput from "./ui/MoneyInput.vue";
import NumberInput from "./ui/NumberInput.vue";
import ToggleSwitch from "primevue/toggleswitch";
import { computed, ref, watch } from "vue";
import { useId } from "vue";
import type { DealInputModel } from "../types";
import { toNumber } from "../utils/dealUtils";

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
 * Read a numeric field for display. Inputs expect `null` when empty.
 *
 * There is deliberately no default substituted here. Doing so is what made LTV
 * and the long term rate impossible to retype: `set` stored `undefined` on
 * clear, `get` immediately rendered the default back, and the box refilled
 * itself between keystrokes. `SliderField` copes with a `null` on its own
 * (the thumb parks at its low end while the box is empty), and real defaults
 * are seeded once by `createEmptyDealForm` / `ensureBrrrLegacyDefaults`.
 *
 * Goes through `toNumber` because a deal loaded from the API carries its money
 * and percentage fields as *strings* (`"200.00"` — FastAPI serialises `Decimal`
 * that way), while a deal the user is typing into carries real numbers. Checking
 * `typeof === "number"` here would blank out every saved deal's inputs.
 */
function get(key: NumericKey): number | null {
  return toNumber(props.deal[key]) ?? null;
}

/**
 * Write a numeric field back. Clearing an input stores `undefined`, not `0`, so
 * the field is omitted from the payload and the backend default applies.
 *
 * There is deliberately no per-field fallback here. Refi Points, LTV, the long
 * term rate and Cash Reserve used to substitute their default whenever the
 * input went empty, which meant deleting the last digit instantly wrote the
 * default back — you could never blank the box to retype, and backspacing
 * through a value fought you the whole way. Defaults belong at deal creation
 * (`createEmptyDealForm`) and at load (`ensureBrrrLegacyDefaults`), not on
 * every keystroke.
 */
function set(key: NumericKey, value: number | null): void {
  (props.deal as Record<NumericKey, number | undefined>)[key] =
    value ?? undefined;
}

const useHmForRehab = computed({
  get: () => props.deal.use_HM_for_rehab ?? false,
  set: (value: boolean) => {
    props.deal.use_HM_for_rehab = value;
  },
});

const isBrrr = computed(() => props.dealType === "BRRRR");

/** One tab per phase of the deal; `key` is also the `data-form-tab` the e2e fixture reads. */
type PhaseTabKey = "buy" | "rehab" | "rentHolding" | "refinance" | "buyRehab" | "flipStrategy" | "expenses";
interface PhaseTab {
  key: PhaseTabKey;
  label: string;
  /** PrimeIcons name, the same glyph the section header shows. */
  icon: string;
}

const BRRRR_PHASE_TABS: readonly PhaseTab[] = [
  { key: "buy", label: "Buy", icon: "pi-home" },
  { key: "rehab", label: "Rehab", icon: "pi-wrench" },
  { key: "rentHolding", label: "Rent & Holding", icon: "pi-key" },
  { key: "refinance", label: "Refinance", icon: "pi-refresh" },
];
const FLIP_PHASE_TABS: readonly PhaseTab[] = [
  { key: "buyRehab", label: "Buy & Rehab", icon: "pi-home" },
  { key: "flipStrategy", label: "Flip Strategy", icon: "pi-dollar" },
  { key: "expenses", label: "Expenses", icon: "pi-wallet" },
];

const phaseTabs = computed(() => (isBrrr.value ? BRRRR_PHASE_TABS : FLIP_PHASE_TABS));
const activePhaseTabKey = ref<PhaseTabKey>(phaseTabs.value[0]!.key);
/** Switching BRRRR <-> FLIP swaps the tab set, so land on the first tab of the new one. */
watch(
  () => props.dealType,
  () => {
    activePhaseTabKey.value = phaseTabs.value[0]!.key;
  },
);
const isPhaseTabActive = (key: PhaseTabKey) => activePhaseTabKey.value === key;

/**
 * The inputs with no meaningful default that the analysis cannot run without,
 * by the tab that holds them — the same fields that carry
 * `neededToRunAnalysis` on their `MoneyInput`. A tab shows a dot while any of
 * its fields is still empty or 0.
 */
const NEEDED_FIELDS_BY_PHASE_TAB: Record<PhaseTabKey, readonly NumericKey[]> = {
  buy: ["purchasePrice"],
  rehab: ["rehabCost"],
  rentHolding: ["rent", "annual_property_taxes", "annual_insurance"],
  refinance: ["arv_in_thousands"],
  buyRehab: ["purchasePrice", "rehabCost"],
  flipStrategy: ["salePrice"],
  expenses: ["annual_property_taxes", "annual_insurance"],
};
const phaseTabNeedsInput = (key: PhaseTabKey): boolean =>
  NEEDED_FIELDS_BY_PHASE_TAB[key].some((field) => !(toNumber(props.deal[field]) ?? 0));

// Cosmetic divergence kept from the two v1 hosts: the modal names the box more fully.
const sellingBoxHeading = computed(() =>
  props.surface === "panel" ? "Selling Costs Breakdown" : "Selling Costs",
);

/** Populate the three selling-cost fields with the usual flip assumptions. */
const quickCalcSellingCosts = () => {
  props.deal.buyerAgentSellingFee = 3;
  props.deal.sellerAgentSellingFee = 3;
  props.deal.sellingClosingCosts = 5;
};

const hmToggleId = useId();

/**
 * Heading levels follow the host: on the Analyze page the topbar is the h1 and
 * the view's own title the h2, so sections are h3; inside a deal modal the
 * dialog title is the h2, so sections are h3 there too and their sub-boxes h4.
 */
const sectionHeading = computed(() => "h3" as const);
const subHeading = computed(() => "h4" as const);
</script>

<template>
  <!--
    `group` so the two inset boxes below (the HM switch, the flip selling-costs
    panel) can read this root's `data-surface` — they carry none of their own,
    and the three sections that do read theirs directly. Every `data-…:` variant
    compiles to `.class[data-surface="card"]`, which is why the surface can pick
    a colour without a class computed.
  -->
  <div
    data-testid="form.root"
    :data-surface="surface"
    class="group data-[surface=card]:space-y-8 data-[surface=panel]:space-y-6"
  >
  <!--
    BRRRR follows the deal's lifecycle: Buy, Rehab, Rent & Holding, Refinance
    (`components/deal/brrr/`). Each section reads and writes `deal` in place through
    `useDealField` and shows its auto-calculated figures beside the inputs.
  -->
  <!--
    The phase tabs. `UiButton variant="tab"` carries `role="tab"` and
    `aria-selected`, which is also how the e2e fixture tells the active tab.
  -->
  <UiTabs data-testid="form.tabs" aria-label="Deal phase" class="max-w-full">
    <UiButton
      v-for="tab in phaseTabs"
      :key="tab.key"
      :data-testid="`form.tab.${tab.key}`"
      variant="tab"
      :active="isPhaseTabActive(tab.key)"
      @click="activePhaseTabKey = tab.key"
    >
      <i class="pi text-xs" :class="tab.icon" aria-hidden="true"></i>
      {{ tab.label }}
      <template v-if="phaseTabNeedsInput(tab.key)">
        <span
          :data-testid="`form.tab.${tab.key}.needs-input`"
          data-part="needs-input"
          aria-hidden="true"
          class="h-1.5 w-1.5 shrink-0 rounded-full bg-primary"
        ></span>
        <span class="sr-only">needs input</span>
      </template>
    </UiButton>
  </UiTabs>

  <!--
    Each phase in its own `v-show` box, so a section's own state survives a tab
    switch and hidden fields stay in the DOM. `data-form-tab` names the tab that
    owns the box: the e2e `setField` fixture clicks it before typing.
  -->
  <template v-if="isBrrr">
    <div v-show="isPhaseTabActive('buy')" data-form-tab="buy">
      <BuySection :deal="deal" :surface="surface" />
    </div>
    <div v-show="isPhaseTabActive('rehab')" data-form-tab="rehab">
      <RehabSection :deal="deal" :surface="surface" />
    </div>
    <div v-show="isPhaseTabActive('rentHolding')" data-form-tab="rentHolding">
      <RentHoldingSection :deal="deal" :surface="surface" />
    </div>
    <div v-show="isPhaseTabActive('refinance')" data-form-tab="refinance">
      <RefinanceSection :deal="deal" :surface="surface" />
    </div>
  </template>

  <template v-else>
  <!-- FLIP: Buy & Rehab -->
  <!--
    `v-reveal` (no `.stagger`) on each section: the four groups are the form's
    own boxes, so the directive animates the element itself. Mount-time only,
    with no leave hook anywhere in the set, so switching BRRRR <-> FLIP swaps
    groups 2a/2b instantly and the new one fades up. The form also renders
    inside both deal modals, where the same reveal runs once on open.
  -->
  <section
    v-show="isPhaseTabActive('buyRehab')"
    v-reveal
    data-form-tab="buyRehab"
    :data-surface="surface"
    class="rounded-card border-ui border-line p-4 shadow-1 md:p-6
           data-[surface=card]:bg-surface data-[surface=panel]:bg-surface-2"
  >
    <UiSectionHeader :as="sectionHeading" class="mb-4">
      <span class="flex items-center gap-2">
        <span class="grid h-7 w-7 place-items-center rounded-ctl bg-primary/12 text-primary" aria-hidden="true"><i class="pi pi-home text-xs"></i></span> Buy &amp; Rehab
      </span>
    </UiSectionHeader>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <MoneyInput
        data-testid="form.field.purchasePrice"
        :model-value="get('purchasePrice')"
        @update:model-value="(v: number | null) => set('purchasePrice', v)"
        label="Purchase Price"
        :inThousands="true"
        :required="true"
        :needed-to-run-analysis="true"
      />
      <div
        :data-layout="surface === 'panel' ? 'paired' : 'flat'"
        class="data-[layout=flat]:contents
               data-[layout=paired]:grid data-[layout=paired]:grid-cols-2 data-[layout=paired]:gap-2"
      >
        <MoneyInput
          data-testid="form.field.rehabCost"
          :model-value="get('rehabCost')"
          @update:model-value="(v: number | null) => set('rehabCost', v)"
          label="Rehab Cost"
          :inThousands="true"
          :needed-to-run-analysis="true"
        />
        <NumberInput
          data-testid="form.field.rehabContingency"
          :model-value="get('rehabContingency')"
          @update:model-value="(v: number | null) => set('rehabContingency', v)"
          label="Contingency"
          suffix="%"
          :min="0"
          :max="100"
        />
      </div>
      <MoneyInput
        data-testid="form.field.closingCostsBuy"
        :model-value="get('closingCostsBuy')"
        @update:model-value="(v: number | null) => set('closingCostsBuy', v)"
        label="Closing Costs (Buy)"
        :inThousands="true"
      />

      <div class="my-2 border-t border-line pt-4 md:col-span-2">
        <UiSectionHeader :as="subHeading" class="mb-3">
          Hard Money Details
        </UiSectionHeader>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <NumberInput
            data-testid="form.field.down_payment"
            :model-value="get('down_payment')"
            @update:model-value="(v: number | null) => set('down_payment', v)"
            label="Down Payment"
            suffix="%"
            :min="0"
            :max="100"
          />
          <NumberInput
            data-testid="form.field.hmlPoints"
            :model-value="get('hmlPoints')"
            @update:model-value="(v: number | null) => set('hmlPoints', v)"
            label="Points"
            suffix=" pts"
            :min="0"
            :max="100"
          />
          <NumberInput
            data-testid="form.field.HMLInterestRate"
            :model-value="get('HMLInterestRate')"
            @update:model-value="(v: number | null) => set('HMLInterestRate', v)"
            label="Interest Rate"
            suffix="%"
            :min="0"
            :max="100"
          />

          <div
            class="flex items-center justify-between gap-3 rounded-ctl border-ui border-line p-3
                   group-data-[surface=card]:bg-surface-2 group-data-[surface=panel]:bg-surface"
          >
            <label :for="hmToggleId" class="text-sm font-medium text-fg">
              Use HM for Rehab
            </label>
            <ToggleSwitch
              data-testid="form.hm-toggle"
              :input-id="hmToggleId"
              v-model="useHmForRehab"
            />
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- Group 2b: Flip Strategy (FLIP only) -->
  <section
    v-show="isPhaseTabActive('flipStrategy')"
    v-reveal
    data-form-tab="flipStrategy"
    :data-surface="surface"
    class="rounded-card border-ui border-line p-4 shadow-1 md:p-6
           data-[surface=card]:bg-surface data-[surface=panel]:bg-surface-2"
  >
    <UiSectionHeader :as="sectionHeading" class="mb-4">
      <span class="flex items-center gap-2">
        <span class="grid h-7 w-7 place-items-center rounded-ctl bg-warning/12 text-warning" aria-hidden="true"><i class="pi pi-dollar text-xs"></i></span> Flip Strategy
      </span>
    </UiSectionHeader>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <MoneyInput
        data-testid="form.field.salePrice"
        :model-value="get('salePrice')"
        @update:model-value="(v: number | null) => set('salePrice', v)"
        label="Projected Sale Price"
        :inThousands="true"
        :required="true"
        :needed-to-run-analysis="true"
      />
      <NumberInput
        data-testid="form.field.holdingTime"
        :model-value="get('holdingTime')"
        @update:model-value="(v: number | null) => set('holdingTime', v)"
        label="Holding Time"
        suffix=" mos"
        :required="true"
      />

      <div
        class="rounded-card border-ui border-line p-3 md:col-span-2
               group-data-[surface=card]:bg-surface-2
               group-data-[surface=panel]:mt-1 group-data-[surface=panel]:bg-surface"
      >
        <UiSectionHeader :as="subHeading" class="mb-3 items-center">
          {{ sellingBoxHeading }}
          <template #actions>
            <UiButton
              type="button"
              data-testid="form.quick-defaults"
              variant="secondary"
              size="sm"
              class="touch:min-h-11"
              @click="quickCalcSellingCosts"
            >
              Quick Defaults (3%/3%/$5k)
            </UiButton>
          </template>
        </UiSectionHeader>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <NumberInput
            data-testid="form.field.buyerAgentSellingFee"
            :model-value="get('buyerAgentSellingFee')"
            @update:model-value="
              (v: number | null) => set('buyerAgentSellingFee', v)
            "
            label="Buyer Agent Fee"
            suffix="%"
          />
          <NumberInput
            data-testid="form.field.sellerAgentSellingFee"
            :model-value="get('sellerAgentSellingFee')"
            @update:model-value="
              (v: number | null) => set('sellerAgentSellingFee', v)
            "
            label="Seller Agent Fee"
            suffix="%"
          />
          <MoneyInput
            data-testid="form.field.sellingClosingCosts"
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
        data-testid="form.field.capitalGainsTax"
        :model-value="get('capitalGainsTax')"
        @update:model-value="(v: number | null) => set('capitalGainsTax', v)"
        label="Capital Gains Tax Rate"
        suffix="%"
      />
    </div>
  </section>

  <!-- Group 3: Expenses (shared, with per-type extras) -->
  <section
    v-show="isPhaseTabActive('expenses')"
    v-reveal
    data-form-tab="expenses"
    :data-surface="surface"
    class="rounded-card border-ui border-line p-4 shadow-1 md:p-6
           data-[surface=card]:bg-surface data-[surface=panel]:bg-surface-2"
  >
    <UiSectionHeader :as="sectionHeading" class="mb-4">
      <span class="flex items-center gap-2">
        <span
          class="grid h-7 w-7 place-items-center rounded-ctl"
          :class="isBrrr ? 'bg-primary/12 text-primary' : 'bg-warning/12 text-warning'"
          aria-hidden="true"
        ><i class="pi pi-wallet text-xs"></i></span>
        Expenses
      </span>
    </UiSectionHeader>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <MoneyInput
        v-if="isBrrr"
        data-testid="form.field.rent"
        :model-value="get('rent')"
        @update:model-value="(v: number | null) => set('rent', v)"
        label="Monthly Rent"
        :required="true"
      />

      <MoneyInput
        data-testid="form.field.annual_property_taxes"
        :model-value="get('annual_property_taxes')"
        @update:model-value="
          (v: number | null) => set('annual_property_taxes', v)
        "
        label="Annual Taxes"
        :needed-to-run-analysis="true"
      />
      <MoneyInput
        data-testid="form.field.annual_insurance"
        :model-value="get('annual_insurance')"
        @update:model-value="(v: number | null) => set('annual_insurance', v)"
        label="Annual Insurance"
        :needed-to-run-analysis="true"
      />
      <MoneyInput
        data-testid="form.field.montly_hoa"
        :model-value="get('montly_hoa')"
        @update:model-value="(v: number | null) => set('montly_hoa', v)"
        label="Monthly HOA"
      />
      <MoneyInput
        v-if="!isBrrr"
        data-testid="form.field.monthly_utilities"
        :model-value="get('monthly_utilities')"
        @update:model-value="(v: number | null) => set('monthly_utilities', v)"
        label="Monthly Utilities"
      />

      <div
        v-if="isBrrr"
        class="md:col-span-2 grid grid-cols-2 md:grid-cols-4 gap-3 mt-2"
      >
        <NumberInput
          data-testid="form.field.vacancyPercent"
          :model-value="get('vacancyPercent')"
          @update:model-value="(v: number | null) => set('vacancyPercent', v)"
          label="Vacancy"
          suffix="%"
        />
        <NumberInput
          data-testid="form.field.maintenancePercent"
          :model-value="get('maintenancePercent')"
          @update:model-value="
            (v: number | null) => set('maintenancePercent', v)
          "
          label="Maint."
          suffix="%"
        />
        <NumberInput
          data-testid="form.field.capexPercent"
          :model-value="get('capexPercent')"
          @update:model-value="(v: number | null) => set('capexPercent', v)"
          label="CapEx"
          suffix="%"
        />
        <NumberInput
          data-testid="form.field.property_managment_fee_precentages_from_rent"
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

  </template>
  </div>
</template>
