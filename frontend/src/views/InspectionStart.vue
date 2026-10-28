<script setup lang="ts">
/**
 * Start a new inspection: the address, the date (today by default) and the
 * inspector's name, one question at a time. Creating it needs a connection;
 * everything after that keeps working offline.
 */
import { computed, nextTick, ref } from "vue";
import { useRouter } from "vue-router";

import "../inspection/inspectionMotion.css";
import { inspectionApi } from "../api/inspection";
import { rememberInspectionOnDevice } from "../inspection/inspectionRecentOnDevice";

const router = useRouter();

const todayIso = (() => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
})();

const propertyAddress = ref("");
const inspectionDate = ref(todayIso);
const inspectorName = ref("");
const currentStepIndex = ref(0);
const isCreating = ref(false);
const errorMessage = ref<string | null>(null);
const addressInput = ref<HTMLInputElement | null>(null);
const nameInput = ref<HTMLInputElement | null>(null);

const MINIMUM_PROPERTY_ADDRESS_LENGTH = 3;
const isAddressValid = computed(() => propertyAddress.value.trim().length >= MINIMUM_PROPERTY_ADDRESS_LENGTH);
const STEP_TITLES = ["Which property?", "When?", "Who is inspecting?"];

async function goToStep(stepIndex: number) {
  currentStepIndex.value = stepIndex;
  await nextTick();
  if (stepIndex === 2) nameInput.value?.focus();
}

async function startWalkthrough() {
  if (!isAddressValid.value) {
    currentStepIndex.value = 0;
    addressInput.value?.focus();
    return;
  }
  isCreating.value = true;
  errorMessage.value = null;
  try {
    const inspection = await inspectionApi.createInspection({
      property_address: propertyAddress.value.trim(),
      inspection_date: inspectionDate.value || todayIso,
      inspector_name: inspectorName.value.trim() || null,
    });
    rememberInspectionOnDevice({ inspection_id: inspection.id, property_address: inspection.property_address, inspection_date: inspection.inspection_date });
    await router.replace({ name: "inspection-walkthrough", params: { inspectionId: inspection.id } });
  } catch (error: any) {
    errorMessage.value = !error?.response
      ? "No connection. Starting an inspection needs signal for a moment; after that it works offline."
      : typeof error.response.data?.detail === "string"
        ? error.response.data.detail
        : "The inspection could not be started. Check the address and try again.";
  } finally {
    isCreating.value = false;
  }
}
</script>

<template>
  <section class="mx-auto flex min-h-full max-w-xl flex-col px-4 py-8 sm:px-6" data-testid="inspection.start">
    <p class="text-xs font-medium uppercase tracking-[0.14em] text-fg-muted">New inspection · step {{ currentStepIndex + 1 }} of 3</p>
    <ol role="list" class="mt-3 flex gap-1.5" aria-hidden="true">
      <li v-for="(title, index) in STEP_TITLES" :key="title" class="h-1.5 flex-1 rounded-full transition-colors duration-base" :class="index <= currentStepIndex ? 'bg-primary' : 'bg-surface-2'"></li>
    </ol>

    <form class="mt-8 flex flex-1 flex-col" @submit.prevent="currentStepIndex < 2 ? goToStep(currentStepIndex + 1) : startWalkthrough()">
      <div :key="currentStepIndex" class="inspection-question-reveal">
        <h1 class="font-display text-4xl leading-tight text-fg">{{ STEP_TITLES[currentStepIndex] }}</h1>

        <label v-if="currentStepIndex === 0" class="mt-6 block">
          <span class="mb-2 block text-base text-fg-muted">Property address</span>
          <input
            ref="addressInput"
            v-model="propertyAddress"
            data-testid="inspection.start.address"
            autocomplete="street-address"
            maxlength="300"
            required
            autofocus
            placeholder="12 Palm Ave, Tampa, FL"
            class="ui-input min-h-14 w-full text-lg"
          />
        </label>

        <label v-else-if="currentStepIndex === 1" class="mt-6 block">
          <span class="mb-2 block text-base text-fg-muted">Inspection date</span>
          <input v-model="inspectionDate" data-testid="inspection.start.date" type="date" class="ui-input min-h-14 w-full max-w-xs text-lg" />
          <button v-if="inspectionDate !== todayIso" type="button" class="mt-2 min-h-11 text-sm text-primary underline-offset-4 hover:underline" @click="inspectionDate = todayIso">Use today</button>
        </label>

        <label v-else class="mt-6 block">
          <span class="mb-2 block text-base text-fg-muted">Inspector name <span class="text-fg-muted/80">(optional)</span></span>
          <input ref="nameInput" v-model="inspectorName" data-testid="inspection.start.inspector" autocomplete="name" maxlength="120" class="ui-input min-h-14 w-full text-lg" />
        </label>
      </div>

      <p v-if="errorMessage" role="alert" data-testid="inspection.start.error" class="mt-4 text-sm text-negative">{{ errorMessage }}</p>

      <div class="mt-auto flex gap-3 pt-10">
        <UiButton v-if="currentStepIndex > 0" variant="secondary" size="lg" data-testid="inspection.start.back" @click="goToStep(currentStepIndex - 1)">
          <i class="pi pi-arrow-left" aria-hidden="true"></i><span class="sr-only">Back</span>
        </UiButton>
        <UiButton
          v-if="currentStepIndex < 2"
          type="submit"
          size="lg"
          block
          data-testid="inspection.start.next"
          :disabled="currentStepIndex === 0 && !isAddressValid"
        >
          Next <i class="pi pi-arrow-right ml-2" aria-hidden="true"></i>
        </UiButton>
        <UiButton v-else type="submit" size="lg" block :loading="isCreating" data-testid="inspection.start.begin">
          <i class="pi pi-play mr-2" aria-hidden="true"></i>Start walkthrough
        </UiButton>
      </div>
    </form>
  </section>
</template>
