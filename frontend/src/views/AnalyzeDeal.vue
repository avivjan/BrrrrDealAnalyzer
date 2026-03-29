<script setup lang="ts">
import { ref, watch, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useDealStore } from "../stores/dealStore";
import MoneyInput from "../components/ui/MoneyInput.vue";
import NumberInput from "../components/ui/NumberInput.vue";
import SliderField from "../components/ui/SliderField.vue";
import ToggleSwitch from "primevue/toggleswitch";

console.group("View: AnalyzeDeal");
console.log("Component setup started");

const store = useDealStore();
const router = useRouter();

const selectedType = ref<"BRRRR" | "FLIP">("BRRRR");

const form = ref({
  // Shared
  purchasePrice: 0,
  rehabCost: 0,
  rehabContingency: 0,
  closingCostsBuy: 0,
  down_payment: 0,
  hmlPoints: 0,
  HMLInterestRate: 11,
  use_HM_for_rehab: false,

  annual_property_taxes: 0,
  annual_insurance: 0,
  montly_hoa: 0,

  // BRRRR Specific
  arv_in_thousands: 0,
  monthsUntilRefi: 6,
  closingCostsRefi: 0,
  loanTermYears: 30,
  ltv_as_precent: 75,
  interestRate: 6.5,
  rent: 0,
  vacancyPercent: 5,
  property_managment_fee_precentages_from_rent: 0,
  maintenancePercent: 5,
  capexPercent: 5,

  // Flip Specific
  salePrice: 0,
  holdingTime: 6,
  buyerAgentSellingFee: 0,
  sellerAgentSellingFee: 0,
  sellingClosingCosts: 0,
  capitalGainsTax: 0,
  monthly_utilities: 0,
});

watch(
  () => form.value.arv_in_thousands,
  (val) => {
    if (selectedType.value === "BRRRR") form.value.salePrice = val;
  }
);
watch(
  () => form.value.salePrice,
  (val) => {
    if (selectedType.value === "FLIP") form.value.arv_in_thousands = val;
  }
);

onMounted(() => {
  console.log("View: AnalyzeDeal mounted");
});

const validationErrors = ref<string[]>([]);

const validateForm = () => {
  const errors: string[] = [];
  const f = form.value;

  if (!f.purchasePrice || f.purchasePrice <= 0)
    errors.push("Purchase price (in thousands) must be greater than 0.");
  if (f.rehabCost < 0)
    errors.push("Rehab cost (in thousands) cannot be negative.");
  if (f.rehabContingency < 0 || f.rehabContingency > 100)
    errors.push("Contingency must be between 0% and 100%.");
  if (f.down_payment < 0 || f.down_payment > 100)
    errors.push("Down payment percentage must be between 0% and 100%.");

  if (selectedType.value === "BRRRR") {
    if (!f.arv_in_thousands || f.arv_in_thousands <= 0)
      errors.push("ARV (in thousands) must be greater than 0.");
    if (!f.rent || f.rent <= 0) errors.push("Rent must be greater than 0.");
    if (f.ltv_as_precent <= 0 || f.ltv_as_precent > 100)
      errors.push("LTV must be between 0% and 100%.");
  } else {
    if (!f.salePrice || f.salePrice <= 0)
      errors.push("Sale Price (ARV) must be greater than 0.");
    if (f.holdingTime <= 0) errors.push("Holding time must be greater than 0.");
    if (f.buyerAgentSellingFee < 0 || f.buyerAgentSellingFee > 100)
      errors.push("Buyer agent fee must be between 0% and 100%.");
    if (f.sellerAgentSellingFee < 0 || f.sellerAgentSellingFee > 100)
      errors.push("Seller agent fee must be between 0% and 100%.");
    if (f.sellingClosingCosts < 0)
      errors.push("Closing costs cannot be negative.");
  }

  return errors;
};

const onAnalyzeAndSaveClick = () => {
  const errors = validateForm();
  if (errors.length > 0) {
    validationErrors.value = errors;
    return;
  }
  validationErrors.value = [];
  showSaveModal.value = true;
};

// Save Modal Logic
const showSaveModal = ref(false);
const isSaving = ref(false);
const saveError = ref("");
const saveForm = ref({
  address: "",
  section: 1,
  stage: 2,
});

const saveDeal = async () => {
  if (!saveForm.value.address.trim()) {
    saveError.value = "Property address is required.";
    return;
  }
  saveError.value = "";
  isSaving.value = true;

  try {
    const dealData = {
      ...form.value,
      ...saveForm.value,
      deal_type: selectedType.value,
    };
    const savedDeal = await store.saveDeal(dealData as any);
    showSaveModal.value = false;

    await router.push({
      path: "/my-deals",
      query: {
        openDeal: savedDeal.id,
        dealType: savedDeal.deal_type || selectedType.value,
        section: String(saveForm.value.section),
      },
    });
  } catch (e) {
    console.error("View: AnalyzeDeal - save failed:", e);
    saveError.value = "Failed to save deal. Please try again.";
  } finally {
    isSaving.value = false;
  }
};

const quickCalcSellingCosts = () => {
  form.value.buyerAgentSellingFee = 3;
  form.value.sellerAgentSellingFee = 3;
  form.value.sellingClosingCosts = 5;
};
</script>

<template>
  <div class="min-h-screen bg-gray-50 text-gray-900 p-4 pb-24 md:p-8">
    <div class="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-8">
      <!-- Left Column: Form -->
      <div class="lg:col-span-2 space-y-8">
        <header
          class="flex flex-col md:flex-row justify-between items-center mb-6 gap-4"
        >
          <h1
            class="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600"
          >
            Analyze Deal
          </h1>

          <!-- Type Switcher -->
          <div
            class="bg-white p-1 rounded-xl shadow-sm border border-gray-200 flex"
          >
            <button
              @click="selectedType = 'BRRRR'"
              :class="
                selectedType === 'BRRRR'
                  ? 'bg-blue-100 text-blue-700 font-bold'
                  : 'text-gray-500 hover:text-gray-700'
              "
              class="px-6 py-2 rounded-lg transition-all"
            >
              BRRRR
            </button>
            <button
              @click="selectedType = 'FLIP'"
              :class="
                selectedType === 'FLIP'
                  ? 'bg-orange-100 text-orange-700 font-bold'
                  : 'text-gray-500 hover:text-gray-700'
              "
              class="px-6 py-2 rounded-lg transition-all"
            >
              FLIP
            </button>
          </div>

          <button
            @click="$router.push('/')"
            class="text-gray-500 hover:text-blue-600 transition-colors"
          >
            <i class="pi pi-home text-xl"></i>
          </button>
        </header>

        <!-- Group 1: Buy & Rehab (Shared) -->
        <section
          class="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm"
        >
          <h2
            class="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2"
          >
            <i class="pi pi-home text-blue-500"></i> Buy & Rehab
          </h2>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <MoneyInput
              v-model="form.purchasePrice"
              label="Purchase Price"
              :inThousands="true"
              required
            />
            <MoneyInput
              v-model="form.rehabCost"
              label="Rehab Cost"
              :inThousands="true"
            />
            <NumberInput
              v-model="form.rehabContingency"
              label="Contingency"
              suffix="%"
              :min="0"
              :max="100"
            />
            <MoneyInput
              v-model="form.closingCostsBuy"
              label="Closing Costs (Buy)"
              :inThousands="true"
            />

            <div class="md:col-span-2 border-t border-gray-200 my-2 pt-4">
              <h3 class="text-sm font-semibold text-gray-600 mb-3">
                Hard Money Details
              </h3>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <NumberInput
                  v-model="form.down_payment"
                  label="Down Payment"
                  suffix="%"
                  :min="0"
                  :max="100"
                />
                <NumberInput
                  v-model="form.hmlPoints"
                  label="Points"
                  suffix=" pts"
                  :min="0"
                  :max="100"
                />
                <NumberInput
                  v-model="form.HMLInterestRate"
                  label="Interest Rate"
                  suffix="%"
                  :min="0"
                  :max="100"
                />

                <div
                  class="flex items-center justify-between bg-gray-50 p-3 rounded-lg border border-gray-200"
                >
                  <span class="text-sm font-medium text-gray-700"
                    >Use HM for Rehab</span
                  >
                  <ToggleSwitch
                    v-model="form.use_HM_for_rehab"
                    :pt="{
                      slider: ({ props }) => ({
                        class: props.modelValue ? 'bg-blue-500' : 'bg-gray-400',
                      }),
                    }"
                  />
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- BRRRR Section -->
        <section
          v-if="selectedType === 'BRRRR'"
          class="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm"
        >
          <h2
            class="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2"
          >
            <i class="pi pi-refresh text-blue-500"></i> Refinance (BRRRR)
          </h2>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <MoneyInput
              v-model="form.arv_in_thousands"
              label="ARV"
              :inThousands="true"
              required
            />
            <SliderField
              v-model="form.ltv_as_precent"
              label="LTV"
              :min="1"
              :max="100"
              required
              suffix="%"
            />

            <NumberInput
              v-model="form.monthsUntilRefi"
              label="Months until Refi"
              suffix=" mos"
            />
            <MoneyInput
              v-model="form.closingCostsRefi"
              label="Refi Closing Costs"
              :inThousands="true"
            />

            <SliderField
              v-model="form.interestRate"
              label="Long Term Interest Rate"
              :min="0"
              :max="20"
              :step="0.125"
              suffix="%"
              required
            />
            <NumberInput
              v-model="form.loanTermYears"
              label="Loan Term"
              suffix=" Years"
            />
          </div>
        </section>

        <!-- FLIP Section -->
        <section
          v-if="selectedType === 'FLIP'"
          class="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm"
        >
          <h2
            class="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2"
          >
            <i class="pi pi-dollar text-orange-500"></i> Flip Strategy
          </h2>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <MoneyInput
              v-model="form.salePrice"
              label="Projected Sale Price"
              :inThousands="true"
              required
            />
            <NumberInput
              v-model="form.holdingTime"
              label="Holding Time"
              suffix=" mos"
              required
            />

            <div
              class="md:col-span-2 bg-gray-50 rounded-lg p-3 border border-gray-100"
            >
              <div class="flex justify-between items-center mb-3">
                <h3 class="text-sm font-semibold text-gray-700">
                  Selling Costs
                </h3>
                <button
                  @click="quickCalcSellingCosts"
                  class="px-2 py-1 text-xs bg-white border border-gray-200 rounded hover:bg-gray-50 text-gray-600 transition-colors shadow-sm"
                >
                  Quick Defaults (3%/3%/$5k)
                </button>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <NumberInput
                  v-model="form.buyerAgentSellingFee"
                  label="Buyer Agent Fee"
                  suffix="%"
                />
                <NumberInput
                  v-model="form.sellerAgentSellingFee"
                  label="Seller Agent Fee"
                  suffix="%"
                />
                <MoneyInput
                  v-model="form.sellingClosingCosts"
                  label="Closing Costs"
                  :inThousands="true"
                />
              </div>
            </div>

            <NumberInput
              v-model="form.capitalGainsTax"
              label="Capital Gains Tax Rate"
              suffix="%"
            />
          </div>
        </section>

        <!-- Expenses (Shared but customized) -->
        <section
          class="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm"
        >
          <h2
            class="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2"
          >
            <i
              class="pi pi-wallet"
              :class="
                selectedType === 'BRRRR' ? 'text-blue-500' : 'text-orange-500'
              "
            ></i>
            Expenses
          </h2>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <MoneyInput
              v-if="selectedType === 'BRRRR'"
              v-model="form.rent"
              label="Monthly Rent"
              required
            />

            <MoneyInput
              v-model="form.annual_property_taxes"
              label="Annual Taxes"
            />
            <MoneyInput
              v-model="form.annual_insurance"
              label="Annual Insurance"
            />
            <MoneyInput v-model="form.montly_hoa" label="Monthly HOA" />
            <MoneyInput
              v-if="selectedType === 'FLIP'"
              v-model="form.monthly_utilities"
              label="Monthly Utilities"
            />

            <div
              v-if="selectedType === 'BRRRR'"
              class="md:col-span-2 grid grid-cols-2 md:grid-cols-4 gap-3 mt-2"
            >
              <NumberInput
                v-model="form.vacancyPercent"
                label="Vacancy"
                suffix="%"
              />
              <NumberInput
                v-model="form.maintenancePercent"
                label="Maint."
                suffix="%"
              />
              <NumberInput
                v-model="form.capexPercent"
                label="CapEx"
                suffix="%"
              />
              <NumberInput
                v-model="form.property_managment_fee_precentages_from_rent"
                label="Prop. Mgmt"
                suffix="%"
              />
            </div>
          </div>
        </section>

        <!-- Analyze & Save Button -->
        <div class="flex flex-col items-end pt-2 gap-2">
          <div
            v-if="validationErrors.length > 0"
            class="flex flex-col items-end gap-1 w-full"
          >
            <div
              v-for="(error, index) in validationErrors"
              :key="index"
              class="text-red-500 text-sm font-medium animate-pulse flex items-center justify-end"
            >
              <i class="pi pi-exclamation-circle mr-1"></i>
              {{ error }}
            </div>
          </div>
          <button
            @click="onAnalyzeAndSaveClick"
            class="w-full md:w-auto text-white font-bold py-3 px-8 rounded-xl shadow-lg transition-all transform hover:scale-[1.02] active:scale-95 flex items-center justify-center gap-2 text-lg"
            :class="
              selectedType === 'BRRRR'
                ? 'bg-blue-600 hover:bg-blue-700'
                : 'bg-orange-500 hover:bg-orange-600'
            "
          >
            <i class="pi pi-bolt"></i> Analyze & Save
          </button>
        </div>
      </div>

      <!-- Right Column: Info & Navigation (Sticky) -->
      <div class="lg:col-span-1">
        <div class="sticky top-6 space-y-6">
          <!-- How It Works Card -->
          <div
            class="bg-white p-6 rounded-2xl border border-gray-200 shadow-xl relative overflow-hidden"
          >
            <div
              class="absolute top-0 left-0 w-full h-1"
              :class="
                selectedType === 'BRRRR'
                  ? 'bg-gradient-to-r from-blue-500 to-indigo-500'
                  : 'bg-gradient-to-r from-orange-400 to-red-500'
              "
            ></div>

            <h2
              class="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2"
            >
              <i
                class="pi pi-info-circle"
                :class="
                  selectedType === 'BRRRR' ? 'text-blue-500' : 'text-orange-500'
                "
              ></i>
              How It Works
            </h2>

            <div class="space-y-4">
              <div class="flex items-start gap-3">
                <div class="flex-none w-7 h-7 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-sm font-bold">1</div>
                <div>
                  <p class="text-sm font-medium text-gray-800">Fill in deal numbers</p>
                  <p class="text-xs text-gray-500 mt-0.5">Enter purchase price, rehab, financing details, and expenses.</p>
                </div>
              </div>
              <div class="flex items-start gap-3">
                <div class="flex-none w-7 h-7 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-sm font-bold">2</div>
                <div>
                  <p class="text-sm font-medium text-gray-800">Analyze & Save</p>
                  <p class="text-xs text-gray-500 mt-0.5">Click the button, enter the property address, and save it to your board.</p>
                </div>
              </div>
              <div class="flex items-start gap-3">
                <div class="flex-none w-7 h-7 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center text-sm font-bold">3</div>
                <div>
                  <p class="text-sm font-medium text-gray-800">See results & refine</p>
                  <p class="text-xs text-gray-500 mt-0.5">View full analysis on your deal board. Changes auto-save as you tweak numbers.</p>
                </div>
              </div>
            </div>

            <div class="mt-6 p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <p class="text-xs text-amber-700 flex items-start gap-2">
                <i class="pi pi-shield text-amber-500 mt-0.5 flex-none"></i>
                Every deal is automatically saved &mdash; no more lost data during busy days.
              </p>
            </div>
          </div>

          <!-- My Deals Button -->
          <button
            @click="$router.push('/my-deals')"
            class="w-full bg-white hover:bg-gray-50 border border-gray-200 text-gray-700 font-bold py-3 px-4 rounded-xl shadow-sm transition-all transform hover:scale-[1.02] active:scale-95 flex items-center justify-center gap-2"
          >
            <i class="pi pi-list"></i> My Deals
          </button>
        </div>
      </div>
    </div>

    <!-- Save Modal Overlay -->
    <div
      v-if="showSaveModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      @click.self="!isSaving && (showSaveModal = false)"
    >
      <div
        class="bg-white w-full max-w-lg rounded-2xl p-6 border border-gray-200 shadow-2xl animate-fade-in-up"
      >
        <h3 class="text-2xl font-bold text-gray-900 mb-1">Analyze & Save Deal</h3>
        <p class="text-gray-500 text-sm mb-6">
          Enter additional details to add this deal to your board. You'll see the full analysis results after saving.
        </p>

        <div class="space-y-4">
          <div class="flex flex-col gap-1.5">
            <label class="text-sm font-medium text-gray-700"
              >Property Address *</label
            >
            <input
              v-model="saveForm.address"
              class="w-full bg-white border rounded-lg px-3 py-2 text-gray-900 focus:ring-2 focus:ring-blue-500 outline-none transition-colors"
              :class="saveError && !saveForm.address.trim() ? 'border-red-400' : 'border-gray-300'"
              placeholder="123 Main St"
              @keyup.enter="saveDeal"
            />
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div class="flex flex-col gap-1.5">
              <label class="text-sm font-medium text-gray-700">Section</label>
              <select
                v-model="saveForm.section"
                class="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-gray-900 focus:ring-2 focus:ring-blue-500 outline-none appearance-none"
              >
                <option :value="1">Wholesale</option>
                <option :value="2">Market</option>
                <option :value="3">Off Market</option>
              </select>
            </div>
            <div class="flex flex-col gap-1.5">
              <label class="text-sm font-medium text-gray-700">Stage</label>
              <select
                v-model="saveForm.stage"
                class="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-gray-900 focus:ring-2 focus:ring-blue-500 outline-none appearance-none"
              >
                <option :value="1">New - need to analyze</option>
                <option :value="2">Working</option>
                <option :value="3">Brought</option>
                <option :value="4">Keep in Mind</option>
                <option :value="5">Dead</option>
              </select>
            </div>
          </div>
        </div>

        <div v-if="saveError" class="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p class="text-sm text-red-600 flex items-center gap-2">
            <i class="pi pi-exclamation-circle"></i>
            {{ saveError }}
          </p>
        </div>

        <div class="flex justify-end gap-3 mt-8">
          <button
            @click="showSaveModal = false"
            :disabled="isSaving"
            class="px-4 py-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            @click="saveDeal"
            :disabled="isSaving"
            class="px-6 py-2 text-white rounded-lg font-medium shadow-lg transition-all flex items-center gap-2 disabled:opacity-70"
            :class="
              selectedType === 'BRRRR'
                ? 'bg-blue-600 hover:bg-blue-700'
                : 'bg-orange-500 hover:bg-orange-600'
            "
          >
            <i v-if="isSaving" class="pi pi-spin pi-spinner"></i>
            <i v-else class="pi pi-bolt"></i>
            {{ isSaving ? 'Saving...' : 'Analyze & Save' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes fade-in-up {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.animate-fade-in-up {
  animation: fade-in-up 0.3s ease-out forwards;
}
</style>
