<script setup lang="ts">
import { ref, watch, onMounted } from "vue";
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
    The page ground. `pb-safe-b` sits on this box and the real padding on the
    one inside it, so the home-indicator inset is *added* below the page's own
    bottom padding instead of replacing it (the inset is 0 without a notch).
    `min-h-dvh` rather than `min-h-screen`: `dvh` excludes the iOS toolbars.
  -->
  <div class="min-h-dvh bg-page pb-safe-b text-fg">
    <div class="p-4 pb-24 md:p-8">
      <div class="mx-auto grid max-w-7xl grid-cols-1 gap-8 lg:grid-cols-3">
        <!-- Left Column: Form -->
        <div class="space-y-8 lg:col-span-2">
          <!--
            Still a `<header>`: it is the page's banner landmark, and the axe
            baseline counts everything it holds as being inside one.
          -->
          <header>
            <UiSectionHeader as="h1" class="flex-wrap md:items-center">
              Analyze Deal

              <template #actions>
                <!-- Type Switcher -->
                <UiTabs aria-label="Deal type">
                  <UiButton
                    data-testid="analyze.type-brrrr"
                    variant="tab"
                    :active="selectedType === 'BRRRR'"
                    @click="selectedType = 'BRRRR'"
                  >
                    BRRRR
                  </UiButton>
                  <UiButton
                    data-testid="analyze.type-flip"
                    variant="tab"
                    :active="selectedType === 'FLIP'"
                    @click="selectedType = 'FLIP'"
                  >
                    FLIP
                  </UiButton>
                </UiTabs>

                <UiIconButton
                  data-testid="analyze.home"
                  label="Home"
                  size="md"
                  @click="$router.push('/')"
                >
                  <i class="pi pi-home text-xl" aria-hidden="true"></i>
                </UiIconButton>
              </template>
            </UiSectionHeader>
          </header>

          <DealInputsForm
            :deal="form"
            :deal-type="selectedType"
            surface="card"
          />

          <!-- Analyze & Save Button -->
          <div class="flex flex-col gap-3 pt-2 md:items-end">
            <!--
              Static emphasis rather than `animate-pulse`: the muted card, the
              negative border and the negative icon carry the alarm, and the
              message keeps `text-fg` so it clears 4.5:1 on the muted ground
              (`text-negative` there is 4.41:1). Phase 4 adds the enter motion.
            -->
            <UiCard
              v-if="validationErrors.length > 0"
              data-testid="analyze.errors"
              tone="muted"
              padding="sm"
              class="w-full border-negative/40"
            >
              <div class="flex flex-col gap-1.5">
                <div
                  v-for="(error, index) in validationErrors"
                  :key="index"
                  :data-testid="`analyze.error.${index}`"
                  class="flex items-start gap-2 text-sm font-medium text-fg"
                >
                  <i
                    class="pi pi-exclamation-circle mt-0.5 flex-none text-negative"
                    aria-hidden="true"
                  ></i>
                  {{ error }}
                </div>
              </div>
            </UiCard>
            <UiButton
              data-testid="analyze.analyze-save"
              :variant="selectedType === 'FLIP' ? 'flip' : 'brrrr'"
              size="lg"
              class="w-full shadow-2 md:w-auto"
              @click="onAnalyzeAndSaveClick"
            >
              <i class="pi pi-bolt" aria-hidden="true"></i> Analyze & Save
            </UiButton>
          </div>
        </div>

        <!-- Right Column: Info & Navigation (Sticky) -->
        <div class="lg:col-span-1">
          <div class="sticky top-6 space-y-6">
            <!-- How It Works Card -->
            <!--
              `v-reveal` (no `.stagger`): this card *is* the section, so the
              directive animates the element itself. Mount-time only — there is
              no leave, so the sticky column never holds a departing box.
            -->
            <UiCard v-reveal tone="elevated" padding="lg" class="relative overflow-hidden">
              <div
                class="absolute inset-x-0 top-0 h-1"
                :class="selectedType === 'BRRRR' ? 'bg-primary' : 'bg-warning'"
              ></div>

              <h2 class="mb-4 flex items-center gap-2 text-lg font-semibold text-fg">
                <i
                  class="pi pi-info-circle"
                  aria-hidden="true"
                  :class="selectedType === 'BRRRR' ? 'text-primary' : 'text-warning'"
                ></i>
                How It Works
              </h2>

              <div class="space-y-4">
                <div class="flex items-start gap-3">
                  <div class="flex h-7 w-7 flex-none items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">1</div>
                  <div>
                    <p class="text-sm font-medium text-fg">Fill in deal numbers</p>
                    <p class="mt-0.5 text-xs text-fg-muted">Enter purchase price, rehab, financing details, and expenses.</p>
                  </div>
                </div>
                <div class="flex items-start gap-3">
                  <div class="flex h-7 w-7 flex-none items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">2</div>
                  <div>
                    <p class="text-sm font-medium text-fg">Analyze & Save</p>
                    <p class="mt-0.5 text-xs text-fg-muted">Click the button, enter the property address, and save it to your board.</p>
                  </div>
                </div>
                <div class="flex items-start gap-3">
                  <div class="flex h-7 w-7 flex-none items-center justify-center rounded-full bg-positive/10 text-sm font-bold text-positive">3</div>
                  <div>
                    <p class="text-sm font-medium text-fg">See results & refine</p>
                    <p class="mt-0.5 text-xs text-fg-muted">View full analysis on your deal board. Changes auto-save as you tweak numbers.</p>
                  </div>
                </div>
              </div>

              <!--
                `bg-warning/5`, not `/10`: `text-warning` on the 10% wash is
                4.38:1 at 12px, and on the 5% wash 4.70:1.
              -->
              <div class="mt-6 rounded-ctl border border-warning/30 bg-warning/5 p-3">
                <p class="flex items-start gap-2 text-xs text-warning">
                  <i class="pi pi-shield mt-0.5 flex-none" aria-hidden="true"></i>
                  Every deal is automatically saved &mdash; no more lost data during busy days.
                </p>
              </div>
            </UiCard>

            <!-- My Deals Button -->
            <UiButton
              data-testid="analyze.my-deals"
              variant="secondary"
              block
              @click="$router.push('/my-deals')"
            >
              <i class="pi pi-list" aria-hidden="true"></i> My Deals
            </UiButton>
          </div>
        </div>
      </div>
    </div>

    <!--
      Save Modal Overlay. The overlay stays a raw `div`: it owns the
      `@click.self` that closes the modal, and `backdrop-blur` is `md:`-only
      over a solid-enough scrim so a phone gets the scrim and no blur cost.

      `UiTransition` wraps the overlay rather than the panel, and the `modal`
      preset fades the overlay while scaling `[data-ui="modal-panel"]` inside
      it — the fixed box is never transformed. It replaces the scoped
      `fade-in-up` keyframe this file used to carry, which is why there is no
      `<style>` block left: one shared preset, one 150 ms leave that sets
      `pointer-events: none` first, and reduced motion handled centrally.
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

            <!-- One column on a phone: "New - need to analyze" does not fit two. -->
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
            class="mt-4 rounded-ctl border border-negative/40 bg-negative/5 p-3"
          >
            <p class="flex items-center gap-2 text-sm text-fg">
              <i class="pi pi-exclamation-circle flex-none text-negative" aria-hidden="true"></i>
              {{ saveError }}
            </p>
          </div>

          <template #footer>
            <div class="flex justify-end gap-3">
              <UiButton
                data-testid="analyze.modal.cancel"
                variant="secondary"
                @click="showSaveModal = false"
                :disabled="isSaving"
              >
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
