<script setup lang="ts">
import { ref, watch } from "vue";
import { useDealStore } from "../stores/dealStore";
import { storeToRefs } from "pinia";
import MoneyInput from "../components/ui/MoneyInput.vue";
import NumberInput from "../components/ui/NumberInput.vue";
import SliderField from "../components/ui/SliderField.vue";
import ToggleSwitch from "primevue/toggleswitch";
import type { AnalyzeDealReq } from "../types";

const store = useDealStore();
const { currentAnalysisResult, isLoading } = storeToRefs(store);

// Initial form state with defaults from backend model
const form = ref<AnalyzeDealReq>({
  arv_in_thousands: 0,
  purchasePrice: 0,
  rehabCost: 0,
  down_payment: 0,
  closingCostsBuy: 0,
  use_HM_for_rehab: false,
  hmlPoints: 0,
  monthsUntilRefi: 6,
  HMLInterestRate: 10,
  closingCostsRefi: 0,
  loanTermYears: 30,
  ltv_as_precent: 75,
  interestRate: 7,
  rent: 0,
  vacancyPercent: 5,
  property_managment_fee_precentages_from_rent: 0,
  maintenancePercent: 5,
  capexPercent: 5,
  annual_property_taxes: 0,
  annual_insurance: 0,
  montly_hoa: 0,
});

// Analyze Logic
const hasAnalyzed = ref(false);
const validationErrors = ref<string[]>([]);

const validateForm = () => {
  const errors: string[] = [];
  const f = form.value;

  if (!f.arv_in_thousands || f.arv_in_thousands <= 0)
    errors.push("ARV (in thousands) must be greater than 0.");
  if (!f.purchasePrice || f.purchasePrice <= 0)
    errors.push("Purchase price (in thousands) must be greater than 0.");
  if (f.rehabCost < 0)
    errors.push("Rehab cost (in thousands) cannot be negative.");
  if (f.closingCostsBuy < 0)
    errors.push("Closing costs (buy) cannot be negative.");
  if (f.closingCostsRefi < 0)
    errors.push("Refi closing costs (in thousands) cannot be negative.");

  // Lending Terms
  if (f.down_payment < 0 || f.down_payment > 100)
    errors.push("Down payment percentage must be between 0% and 100%.");
  if (f.ltv_as_precent <= 0 || f.ltv_as_precent > 100)
    errors.push("LTV must be between 0% and 100%.");
  if (f.hmlPoints < 0 || f.hmlPoints > 100)
    errors.push("HML points must be between 0% and 100%.");
  if (f.HMLInterestRate <= 0 || f.HMLInterestRate > 100)
    errors.push("HML interest rate must be between 0% and 100%.");

  if (f.monthsUntilRefi <= 0)
    errors.push("Months until refi must be a positive number.");
  if (f.loanTermYears <= 0) errors.push("Loan term must be at least 1 year.");

  // DSCR long-term financing
  if (f.interestRate <= 0 || f.interestRate > 100)
    errors.push("Interest rate must be between 0% and 100%.");

  // Rent + Operating Expenses
  if (!f.rent || f.rent <= 0) errors.push("Rent must be greater than 0.");
  if (f.vacancyPercent < 0 || f.vacancyPercent > 100)
    errors.push("Vacancy percentage must be between 0% and 100%.");
  if (
    f.property_managment_fee_precentages_from_rent < 0 ||
    f.property_managment_fee_precentages_from_rent > 100
  )
    errors.push("Property management percentage must be between 0% and 100%.");
  if (f.maintenancePercent < 0 || f.maintenancePercent > 100)
    errors.push("Maintenance percentage must be between 0% and 100%.");
  if (f.capexPercent < 0 || f.capexPercent > 100)
    errors.push("CapEx percentage must be between 0% and 100%.");

  if (f.annual_property_taxes < 0)
    errors.push("Annual property taxes cannot be negative.");
  if (f.annual_insurance < 0)
    errors.push("Annual insurance cannot be negative.");
  if (f.montly_hoa < 0) errors.push("HOA dues cannot be negative.");

  return errors;
};

const analyze = async () => {
  if (
    form.value.purchasePrice > 0 &&
    form.value.arv_in_thousands > 0 &&
    form.value.rent > 0
  ) {
    validationErrors.value = [];
    await store.analyze(form.value);
  }
};

const onAnalyzeClick = async () => {
  const errors = validateForm();

  if (errors.length > 0) {
    validationErrors.value = errors;
    return;
  }

  validationErrors.value = [];
  hasAnalyzed.value = true;
  await analyze();
};

watch(
  form,
  () => {
    if (hasAnalyzed.value) {
      analyze();
    }
  },
  { deep: true }
);

// Formatting Helpers
const formatCurrency = (value: number | undefined) => {
  if (value === undefined || value === null) return "-";
  if (value === -1) return "∞";
  if (value === -2) return "-∞";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
};

const formatPercent = (value: number | undefined) => {
  if (value === undefined || value === null) return "-";
  if (value === -1) return "∞";
  if (value === -2) return "-∞";
  return `${value.toFixed(2)}%`;
};

// Save Modal Logic
const showSaveModal = ref(false);
const saveForm = ref({
  address: "",
  section: 1,
  stage: 1,
});

const getCashFlowColor = (value: number | undefined) => {
  if (value === undefined || value === null) return "text-white";
  if (value >= 100) return "text-emerald-400";
  if (value >= 1) return "text-gray-400";
  return "text-red-400";
};

const getPerformanceColor = (value: number | undefined) => {
  if (value === undefined || value === null) return "text-white";
  if (value === -1) return "text-emerald-400"; // Infinity
  if (value === -2) return "text-red-400"; // -Infinity
  if (value > 0) return "text-emerald-400";
  if (value < 0) return "text-red-400";
  return "text-gray-400";
};

const getDSCRColor = (value: number | undefined) => {
  if (value === undefined || value === null) return "text-white";
  if (value >= 1.2) return "text-emerald-400";
  if (value >= 1.0) return "text-gray-400";
  return "text-red-400";
};

const saveDeal = async () => {
  try {
    const dealData = {
      ...form.value,
      ...saveForm.value,
    };
    await store.saveDeal(dealData as any);
    showSaveModal.value = false;
    alert("Deal Saved Successfully!");
  } catch (e) {
    alert("Failed to save deal.");
  }
};
</script>

<template>
  <div class="min-h-screen bg-whale-dark text-ocean-50 p-4 pb-24 md:p-8">
    <div class="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-8">
      <!-- Left Column: Form -->
      <div class="lg:col-span-2 space-y-8">
        <header class="flex justify-between items-center mb-6">
          <h1
            class="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-ocean-300 to-ocean-100"
          >
            Analyze Deal
          </h1>
          <button
            @click="$router.push('/')"
            class="text-ocean-300 hover:text-white transition-colors"
          >
            <i class="pi pi-home text-xl"></i>
          </button>
        </header>

        <!-- Group 1: Buy & Rehab -->
        <section
          class="bg-whale-surface/50 p-6 rounded-2xl border border-whale-surface shadow-lg backdrop-blur-sm"
        >
          <h2
            class="text-xl font-semibold text-ocean-100 mb-4 flex items-center gap-2"
          >
            <i class="pi pi-home text-ocean-400"></i> Buy & Rehab
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
            <MoneyInput
              v-model="form.closingCostsBuy"
              label="Closing Costs (Buy)"
              :inThousands="true"
            />

            <div class="md:col-span-2 border-t border-whale-surface my-2 pt-4">
              <h3 class="text-sm font-semibold text-ocean-300 mb-3">
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
                  class="flex items-center justify-between bg-whale-surface p-3 rounded-lg border border-whale-surface/50"
                >
                  <span class="text-sm font-medium text-ocean-200"
                    >Use HM for Rehab</span
                  >
                  <ToggleSwitch
                    v-model="form.use_HM_for_rehab"
                    :pt="{
                      slider: ({ props }) => ({
                        class: props.modelValue
                          ? 'bg-ocean-500'
                          : 'bg-gray-600',
                      }),
                    }"
                  />
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- Group 2: Refinance -->
        <section
          class="bg-whale-surface/50 p-6 rounded-2xl border border-whale-surface shadow-lg backdrop-blur-sm"
        >
          <h2
            class="text-xl font-semibold text-ocean-100 mb-4 flex items-center gap-2"
          >
            <i class="pi pi-refresh text-ocean-400"></i> Refinance (BRRRR)
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

        <!-- Group 3: Rent & Expenses -->
        <section
          class="bg-whale-surface/50 p-6 rounded-2xl border border-whale-surface shadow-lg backdrop-blur-sm"
        >
          <h2
            class="text-xl font-semibold text-ocean-100 mb-4 flex items-center gap-2"
          >
            <i class="pi pi-wallet text-ocean-400"></i> Rent & Expenses
          </h2>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <MoneyInput v-model="form.rent" label="Monthly Rent" required />
            <MoneyInput
              v-model="form.annual_property_taxes"
              label="Annual Taxes"
            />
            <MoneyInput
              v-model="form.annual_insurance"
              label="Annual Insurance"
            />
            <MoneyInput v-model="form.montly_hoa" label="Monthly HOA" />

            <div
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

        <!-- Analyze Button -->
        <div class="flex flex-col items-end pt-2 gap-2">
          <div
            v-if="validationErrors.length > 0"
            class="flex flex-col items-end gap-1 w-full"
          >
            <div
              v-for="(error, index) in validationErrors"
              :key="index"
              class="text-red-400 text-sm font-medium animate-pulse flex items-center justify-end"
            >
              <i class="pi pi-exclamation-circle mr-1"></i>
              {{ error }}
            </div>
          </div>
          <button
            @click="onAnalyzeClick"
            class="w-full md:w-auto bg-ocean-600 hover:bg-ocean-500 text-white font-bold py-3 px-8 rounded-xl shadow-lg transition-all transform hover:scale-[1.02] active:scale-95 flex items-center justify-center gap-2 text-lg"
          >
            <i class="pi pi-bolt"></i> Analyze Deal
          </button>
        </div>
      </div>

      <!-- Right Column: Results (Sticky) -->
      <div class="lg:col-span-1">
        <div class="sticky top-6 space-y-6">
          <!-- Results Card -->
          <div
            class="bg-gradient-to-br from-whale-surface to-whale-dark p-6 rounded-2xl border border-ocean-500/30 shadow-2xl relative overflow-hidden group"
          >
            <div
              class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-ocean-500 to-purple-500"
            ></div>

            <h2
              class="text-2xl font-bold text-white mb-6 flex items-center gap-2"
            >
              <i class="pi pi-chart-bar text-ocean-400"></i> Results
            </h2>

            <div v-if="isLoading" class="flex justify-center py-10">
              <i class="pi pi-spin pi-spinner text-4xl text-ocean-500"></i>
            </div>

            <div v-else class="space-y-4">
              <div
                class="flex justify-between items-end pb-2 border-b border-white/10"
              >
                <span class="text-ocean-200">Cash Out</span>
                <span
                  class="text-2xl font-bold"
                  :class="getPerformanceColor(currentAnalysisResult?.cash_out)"
                >
                  {{ formatCurrency(currentAnalysisResult?.cash_out) }}
                </span>
              </div>
              <div
                class="flex justify-between items-end pb-2 border-b border-white/10"
              >
                <span class="text-ocean-200">Total Cash Needed</span>
                <span class="text-xl font-bold text-blue-400">{{
                  formatCurrency(
                    currentAnalysisResult?.total_cash_needed_for_deal
                  )
                }}</span>
              </div>
              <div
                class="flex justify-between items-end pb-2 border-b border-white/10"
              >
                <span class="text-ocean-200">Cash Flow / mo</span>
                <span
                  class="text-lg font-semibold"
                  :class="getCashFlowColor(currentAnalysisResult?.cash_flow)"
                >
                  {{ formatCurrency(currentAnalysisResult?.cash_flow) }}
                </span>
              </div>

              <!-- Secondary Metrics -->
              <div class="grid grid-cols-2 gap-4 mt-4 text-sm">
                <div>
                  <div class="text-gray-400">DSCR</div>
                  <div
                    class="font-medium"
                    :class="getDSCRColor(currentAnalysisResult?.dscr)"
                  >
                    {{ currentAnalysisResult?.dscr?.toFixed(2) ?? "-" }}
                  </div>
                </div>
                <div>
                  <div class="text-gray-400">ROI</div>
                  <div
                    class="font-medium"
                    :class="getPerformanceColor(currentAnalysisResult?.roi)"
                  >
                    {{ formatPercent(currentAnalysisResult?.roi) }}
                  </div>
                </div>
                <div>
                  <div class="text-gray-400">Equity</div>
                  <div
                    class="font-medium"
                    :class="getPerformanceColor(currentAnalysisResult?.equity)"
                  >
                    {{ formatCurrency(currentAnalysisResult?.equity) }}
                  </div>
                </div>
                <div>
                  <div class="text-gray-400">CoC Return</div>
                  <div
                    class="font-medium"
                    :class="
                      getPerformanceColor(currentAnalysisResult?.cash_on_cash)
                    "
                  >
                    {{ formatPercent(currentAnalysisResult?.cash_on_cash) }}
                  </div>
                </div>
              </div>
            </div>

            <!-- Save Button -->
            <button
              @click="showSaveModal = true"
              class="w-full mt-8 bg-ocean-600 hover:bg-ocean-500 text-white font-bold py-3 px-4 rounded-xl shadow-lg transition-all transform hover:scale-[1.02] active:scale-95 flex items-center justify-center gap-2"
            >
              <i class="pi pi-save"></i> Save Deal
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Save Modal Overlay -->
    <div
      v-if="showSaveModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
    >
      <div
        class="bg-whale-surface w-full max-w-lg rounded-2xl p-6 border border-ocean-500/30 shadow-2xl animate-fade-in-up"
      >
        <h3 class="text-2xl font-bold text-white mb-4">Save Deal</h3>
        <p class="text-ocean-200 text-sm mb-6">
          Enter additional details to add this deal to your board.
        </p>

        <div class="space-y-4">
          <div class="flex flex-col gap-1.5">
            <label class="text-sm font-medium text-ocean-200"
              >Property Address *</label
            >
            <input
              v-model="saveForm.address"
              class="w-full bg-whale-dark border border-whale-surface rounded-lg px-3 py-2 text-white focus:ring-2 focus:ring-ocean-500 outline-none"
              placeholder="123 Main St"
            />
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div class="flex flex-col gap-1.5">
              <label class="text-sm font-medium text-ocean-200">Section</label>
              <select
                v-model="saveForm.section"
                class="w-full bg-whale-dark border border-whale-surface rounded-lg px-3 py-2 text-white focus:ring-2 focus:ring-ocean-500 outline-none appearance-none"
              >
                <option :value="1">Wholesale</option>
                <option :value="2">Market</option>
                <option :value="3">Off Market</option>
              </select>
            </div>
            <div class="flex flex-col gap-1.5">
              <label class="text-sm font-medium text-ocean-200">Stage</label>
              <select
                v-model="saveForm.stage"
                class="w-full bg-whale-dark border border-whale-surface rounded-lg px-3 py-2 text-white focus:ring-2 focus:ring-ocean-500 outline-none appearance-none"
              >
                <option :value="1">New</option>
                <option :value="2">Working</option>
                <option :value="3">Brought</option>
                <option :value="4">Keep in Mind</option>
                <option :value="5">Dead</option>
              </select>
            </div>
          </div>
        </div>

        <div class="flex justify-end gap-3 mt-8">
          <button
            @click="showSaveModal = false"
            class="px-4 py-2 rounded-lg text-ocean-200 hover:text-white hover:bg-white/5 transition-colors"
          >
            Cancel
          </button>
          <button
            @click="saveDeal"
            class="px-6 py-2 bg-ocean-600 hover:bg-ocean-500 text-white rounded-lg font-medium shadow-lg transition-colors"
          >
            Save
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
