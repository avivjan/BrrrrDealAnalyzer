<script setup lang="ts">
import { computed, ref, watch, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useDealStore } from "../stores/dealStore";
import { createEmptyDealForm, validateDealInputs } from "../utils/dealUtils";
import DealInputsForm from "../components/DealInputsForm.vue";

console.group("View: AnalyzeDeal");
console.log("Component setup started");

const store = useDealStore();
const router = useRouter();

const selectedType = ref<"BRRRR" | "FLIP">("BRRRR");

const form = ref(createEmptyDealForm(selectedType.value));

watch(selectedType, (type) => {
  form.value.deal_type = type;
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

/** Presentational: the live summary rail echoes three inputs (values are in thousands). */
const fmtK = (value: unknown): string => {
  const n = Number(value);
  if (!Number.isFinite(n) || n === 0) return "—";
  const sign = n < 0 ? "-" : "";
  const a = Math.abs(n);
  return a >= 1000 ? `${sign}$${(a / 1000).toFixed(1)}M` : `${sign}$${a.toLocaleString(undefined, { maximumFractionDigits: 1 })}K`;
};
const summary = computed(() => [
  { label: "Purchase", value: fmtK(form.value.purchasePrice) },
  { label: "Rehab", value: fmtK(form.value.rehabCost) },
  selectedType.value === "BRRRR"
    ? { label: "ARV", value: fmtK(form.value.arv_in_thousands) }
    : { label: "Sale price", value: fmtK(form.value.salePrice) },
]);

const onAnalyzeAndSaveClick = () => {
  const errors = validateDealInputs(form.value, selectedType.value);
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
</script>

<template>
  <!--
    UI v2. The shell owns the viewport, the sticky header and the page title
    ("Analyze a deal", the topbar's h1), so this is a two-column workspace:
    the form on the left, a sticky rail on the right with the strategy switch,
    a live echo of the three numbers that matter most, the validation list and
    the one call to action. Every hook and handler is the v1 one.
  -->
  <div class="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-5 sm:px-6 lg:px-8 lg:py-8">
    <div class="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
      <!-- Left: the inputs -->
      <div class="flex min-w-0 flex-col gap-6">
        <!-- UI v3: the hero header — eyebrow → title → the deal-type tabs. -->
        <UiTransition preset="hero" appear>
          <header class="flex flex-wrap items-end justify-between gap-3">
            <div class="min-w-0 flex-1">
              <p data-hero="eyebrow" class="numeric text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">
                Analyze
              </p>
              <UiSectionHeader
                as="h2"
                data-hero="title"
                class="[&_[data-part=title]]:font-display [&_[data-part=title]]:text-2xl [&_[data-part=title]]:tracking-display"
              >
                New deal
                <template #subtitle>Enter the numbers; the analysis runs when you save.</template>
              </UiSectionHeader>
            </div>
            <UiTabs data-hero="item" aria-label="Deal type" class="max-w-full">
              <UiButton
                data-testid="analyze.type-brrrr"
                variant="tab"
                :active="selectedType === 'BRRRR'"
                @click="selectedType = 'BRRRR'"
              >
                <i class="pi pi-home text-xs" aria-hidden="true"></i> BRRRR
              </UiButton>
              <UiButton
                data-testid="analyze.type-flip"
                variant="tab"
                :active="selectedType === 'FLIP'"
                @click="selectedType = 'FLIP'"
              >
                <i class="pi pi-dollar text-xs" aria-hidden="true"></i> FLIP
              </UiButton>
            </UiTabs>
          </header>
        </UiTransition>

        <DealInputsForm :deal="form" :deal-type="selectedType" surface="card" />
      </div>

      <!-- Right: the sticky rail -->
      <aside aria-label="Deal summary" class="flex flex-col gap-4 lg:sticky lg:top-4">
        <UiSurface v-tilt :level="1" padding="lg" class="flex flex-col gap-5">
          <div class="flex items-center justify-between gap-3">
            <span class="text-[11px] font-semibold uppercase tracking-[0.12em] text-fg-muted">Summary</span>
            <UiBadge :deal-type="selectedType" size="md">{{ selectedType }}</UiBadge>
          </div>

          <dl class="grid grid-cols-3 gap-3">
            <div v-for="row in summary" :key="row.label" class="min-w-0">
              <dt class="truncate text-[11px] uppercase tracking-[0.1em] text-fg-muted">{{ row.label }}</dt>
              <dd v-count-up class="numeric mt-1 truncate text-lg font-semibold text-fg">{{ row.value }}</dd>
            </div>
          </dl>

          <!--
            Static emphasis rather than `animate-pulse`: the negative border and
            the icon carry the alarm; the copy keeps `text-fg` for contrast.
          -->
          <UiSurface
            v-if="validationErrors.length > 0"
            data-testid="analyze.errors"
            :level="2"
            padding="sm"
            role="alert"
            class="border-negative/40"
          >
            <div class="flex flex-col gap-1.5">
              <div
                v-for="(error, index) in validationErrors"
                :key="index"
                :data-testid="`analyze.error.${index}`"
                class="flex items-start gap-2 text-sm font-medium text-fg"
              >
                <i class="pi pi-exclamation-circle mt-0.5 flex-none text-negative" aria-hidden="true"></i>
                {{ error }}
              </div>
            </div>
          </UiSurface>

          <UiButton
            data-testid="analyze.analyze-save"
            :variant="selectedType === 'FLIP' ? 'flip' : 'brrrr'"
            size="lg"
            block
            class="shadow-glow-primary"
            @click="onAnalyzeAndSaveClick"
          >
            <i class="pi pi-bolt" aria-hidden="true"></i> Analyze & Save
          </UiButton>

          <UiButton data-testid="analyze.my-deals" variant="secondary" block @click="$router.push('/my-deals')">
            <i class="pi pi-objects-column" aria-hidden="true"></i> My Deals
          </UiButton>
        </UiSurface>

        <UiSurface :level="1" padding="lg" class="hidden lg:block">
          <h3 class="mb-3 flex items-center gap-2 text-sm font-semibold text-fg">
            <i class="pi pi-info-circle text-primary" aria-hidden="true"></i> How it works
          </h3>
          <ol class="flex flex-col gap-3 text-sm">
            <li class="flex items-start gap-3">
              <span class="numeric grid h-6 w-6 flex-none place-items-center rounded-full bg-primary/12 text-xs font-bold text-primary">1</span>
              <span><span class="font-medium text-fg">Fill in deal numbers.</span> <span class="text-fg-muted">Purchase, rehab, financing, expenses.</span></span>
            </li>
            <li class="flex items-start gap-3">
              <span class="numeric grid h-6 w-6 flex-none place-items-center rounded-full bg-primary/12 text-xs font-bold text-primary">2</span>
              <span><span class="font-medium text-fg">Analyze &amp; Save.</span> <span class="text-fg-muted">Name the property and it lands on your board.</span></span>
            </li>
            <li class="flex items-start gap-3">
              <span class="numeric grid h-6 w-6 flex-none place-items-center rounded-full bg-positive/12 text-xs font-bold text-positive">3</span>
              <span><span class="font-medium text-fg">Refine on the board.</span> <span class="text-fg-muted">Changes auto-save as you tweak numbers.</span></span>
            </li>
          </ol>
        </UiSurface>
      </aside>
    </div>

    <!--
      Save modal. The overlay stays a raw `div` with the `@click.self` close;
      the `modal` preset fades it and scales the panel inside.
    -->
    <UiTransition preset="modal" appear>
      <div
        v-if="showSaveModal"
        data-testid="analyze.modal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-fg/40 p-4 md:backdrop-blur-sm"
        @click.self="!isSaving && (showSaveModal = false)"
      >
        <UiModalPanel size="md">
          <template #header>Analyze & Save Deal</template>

          <p class="text-sm text-fg-muted">
            Enter additional details to add this deal to your board. You'll see the full analysis results after saving.
          </p>

          <div class="mt-6 space-y-4">
            <UiField>
              <template #label>Property Address *</template>
              <template #default="{ id, describedBy }">
                <input
                  data-testid="analyze.modal.address"
                  v-model="saveForm.address"
                  :id="id"
                  :aria-describedby="describedBy"
                  class="ui-input"
                  :class="saveError && !saveForm.address.trim() ? 'ui-input-invalid' : ''"
                  placeholder="123 Main St"
                  @keyup.enter="saveDeal"
                />
              </template>
            </UiField>

            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <UiField>
                <template #label>Section</template>
                <template #default="{ id, describedBy }">
                  <select
                    data-testid="analyze.modal.section"
                    v-model="saveForm.section"
                    :id="id"
                    :aria-describedby="describedBy"
                    class="ui-select"
                  >
                    <option :value="1">Wholesale</option>
                    <option :value="2">Market</option>
                    <option :value="3">Off Market</option>
                  </select>
                </template>
              </UiField>
              <UiField>
                <template #label>Stage</template>
                <template #default="{ id, describedBy }">
                  <select
                    data-testid="analyze.modal.stage"
                    v-model="saveForm.stage"
                    :id="id"
                    :aria-describedby="describedBy"
                    class="ui-select"
                  >
                    <option :value="1">New - need to analyze</option>
                    <option :value="2">Working</option>
                    <option :value="3">Brought</option>
                    <option :value="4">Keep in Mind</option>
                    <option :value="5">Dead</option>
                  </select>
                </template>
              </UiField>
            </div>
          </div>

          <div
            v-if="saveError"
            data-testid="analyze.modal.error"
            role="alert"
            class="mt-4 rounded-ctl border-ui border-negative/40 bg-negative/5 p-3"
          >
            <p class="flex items-center gap-2 text-sm text-fg">
              <i class="pi pi-exclamation-circle flex-none text-negative" aria-hidden="true"></i>
              {{ saveError }}
            </p>
          </div>

          <template #footer>
            <div class="flex justify-end gap-3">
              <UiButton data-testid="analyze.modal.cancel" variant="secondary" @click="showSaveModal = false" :disabled="isSaving">
                Cancel
              </UiButton>
              <UiButton
                data-testid="analyze.modal.save"
                :variant="selectedType === 'FLIP' ? 'flip' : 'brrrr'"
                @click="saveDeal"
                :disabled="isSaving"
              >
                <i v-if="isSaving" class="pi pi-spin pi-spinner" aria-hidden="true"></i>
                <i v-else class="pi pi-bolt" aria-hidden="true"></i>
                {{ isSaving ? 'Saving...' : 'Analyze & Save' }}
              </UiButton>
            </div>
          </template>
        </UiModalPanel>
      </div>
    </UiTransition>
  </div>
</template>
