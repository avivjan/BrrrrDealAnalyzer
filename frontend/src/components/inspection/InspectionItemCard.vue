<script setup lang="ts">
/**
 * One checklist item, as a card that reveals one question at a time:
 * the condition first, then each field (a follow-up appears only once its
 * condition holds, e.g. Septic → last pump date), then photos and notes.
 * An answered question folds into a one-line answer; tap it to change it.
 */
import { computed, ref, watch } from "vue";

import {
  UNKNOWN_FIELD_VALUE,
  cardQuestionsOfItem,
  formatFieldValue,
  isFieldAnswered,
  revealedQuestionCount,
  type InspectionFieldConfig,
  type InspectionFieldValue,
  type InspectionItemConfig,
  type InspectionItemStatus,
} from "../../inspection/inspectionChecklistLogic";
import { INSPECTION_STATUS_APPEARANCE } from "../../inspection/inspectionStatusAppearance";
import { useInspectionStore } from "../../stores/inspectionStore";
import InspectionFieldQuestion from "./InspectionFieldQuestion.vue";
import InspectionPhotoStrip from "./InspectionPhotoStrip.vue";
import InspectionStatusPicker from "./InspectionStatusPicker.vue";

const props = defineProps<{ item: InspectionItemConfig; levelLabel: string }>();

const store = useInspectionStore();
const answers = computed(() => store.answersByItemKey[props.item.key]);
const itemStatus = computed<InspectionItemStatus>(() => answers.value?.item_status ?? "not_checked");
const fieldValues = computed(() => answers.value?.item_field_values ?? {});
const questions = computed(() => cardQuestionsOfItem(props.item, fieldValues.value));
const revealedCount = computed(() => revealedQuestionCount(props.item, answers.value));
const revealedQuestions = computed(() => questions.value.slice(0, revealedCount.value));

/** The answered question the inspector tapped to change (by key), if any. */
const reopenedQuestionKey = ref<string | null>(null);
const questionKey = (question: (typeof questions.value)[number]) => (question.kind === "field" ? question.field.key : question.kind);
watch(
  () => props.item.key,
  () => {
    reopenedQuestionKey.value = null;
    notesDraft.value = answers.value?.item_notes ?? "";
  },
);

function isQuestionOpen(index: number): boolean {
  const question = revealedQuestions.value[index]!;
  if (index === revealedQuestions.value.length - 1) return true;
  return reopenedQuestionKey.value === questionKey(question);
}

function chooseStatus(status: InspectionItemStatus) {
  store.changeItem(props.item.key, { item_status: status });
  reopenedQuestionKey.value = null;
}

/** One-tap answers (a choice, "Unknown") fold at once; a stepper or text stays open for more taps. */
function answerField(field: InspectionFieldConfig, value: InspectionFieldValue | null) {
  store.changeItem(props.item.key, { item_field_values: { [field.key]: value } });
  const isOneTapAnswer = field.type === "choice" || value === UNKNOWN_FIELD_VALUE || value === null;
  reopenedQuestionKey.value = isOneTapAnswer ? null : field.key;
}

const notesDraft = ref(answers.value?.item_notes ?? "");
watch(
  () => answers.value?.item_notes,
  (storedNotes) => {
    if (document.activeElement?.getAttribute("data-testid") !== "inspection.card.notes") notesDraft.value = storedNotes ?? "";
  },
);
function onNotesTyped() {
  store.changeItem(props.item.key, { item_notes: notesDraft.value });
}

const statusAppearance = computed(() => INSPECTION_STATUS_APPEARANCE[itemStatus.value]);
</script>

<template>
  <article class="rounded-panel border border-line bg-surface p-5 shadow-3 sm:p-7" :aria-labelledby="`inspection-item-${item.key}-title`" data-testid="inspection.card">
    <header class="mb-6">
      <p class="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.14em] text-fg-muted">
        {{ levelLabel }}
        <span v-if="item.is_critical" class="inline-flex items-center gap-1 rounded-full bg-accent/15 px-2 py-0.5 text-[11px] font-semibold tracking-wide text-accent" data-testid="inspection.card.critical">
          <i class="pi pi-bolt text-[10px]" aria-hidden="true"></i>Critical
        </span>
      </p>
      <h2 :id="`inspection-item-${item.key}-title`" class="mt-2 font-display text-3xl leading-tight text-fg sm:text-4xl">{{ item.label }}</h2>
      <p class="mt-1 text-base text-fg-muted">{{ item.description }}</p>
    </header>

    <ol role="list" class="space-y-3">
      <li v-for="(question, index) in revealedQuestions" :key="questionKey(question)" class="inspection-question-reveal">
        <!-- Folded answer line -->
        <button
          v-if="!isQuestionOpen(index)"
          type="button"
          :data-testid="`inspection.card.answer.${questionKey(question)}`"
          class="flex min-h-12 w-full items-center justify-between gap-3 rounded-ctl border border-line bg-surface-2/50 px-4 text-left text-base transition-colors duration-fast hover:border-fg-muted"
          @click="reopenedQuestionKey = questionKey(question)"
        >
          <span class="text-fg-muted">{{ question.kind === "status" ? "Condition" : question.kind === "field" ? question.field.label : "Photos & notes" }}</span>
          <span class="flex items-center gap-2 font-semibold" :class="question.kind === 'status' ? statusAppearance.textClass : 'text-fg'">
            <template v-if="question.kind === 'status'"><i :class="statusAppearance.icon" aria-hidden="true"></i>{{ statusAppearance.label }}</template>
            <template v-else-if="question.kind === 'field'">{{ formatFieldValue(question.field, fieldValues[question.field.key]) }}</template>
            <i class="pi pi-pencil text-xs text-fg-muted" aria-hidden="true"></i>
          </span>
        </button>

        <!-- Open question -->
        <div v-else class="rounded-card border border-line/70 bg-page/40 p-4">
          <template v-if="question.kind === 'status'">
            <p class="mb-3 text-base font-semibold text-fg">Condition</p>
            <InspectionStatusPicker :model-value="itemStatus" @update:model-value="chooseStatus" />
          </template>
          <template v-else-if="question.kind === 'field'">
            <InspectionFieldQuestion :field="question.field" :model-value="fieldValues[question.field.key]" @update:model-value="answerField(question.field, $event)" />
            <button
              v-if="question.field.type === 'counter' && !isFieldAnswered(question.field, fieldValues)"
              type="button"
              data-testid="inspection.card.counter-none"
              class="mt-3 min-h-11 text-sm font-medium text-primary underline-offset-4 hover:underline"
              @click="answerField(question.field, 0)"
            >
              None need replacing
            </button>
          </template>
          <template v-else>
            <p class="mb-3 text-base font-semibold text-fg">Photos & notes <span class="font-normal text-fg-muted">(optional)</span></p>
            <InspectionPhotoStrip :item-key="item.key" :item-label="item.label" :photo-prompt="item.photo_prompt" />
            <label class="mt-4 block">
              <span class="sr-only">Notes for {{ item.label }}</span>
              <textarea
                v-model="notesDraft"
                data-testid="inspection.card.notes"
                rows="3"
                maxlength="4000"
                placeholder="Notes (optional)"
                class="ui-textarea w-full text-base"
                @input="onNotesTyped"
              ></textarea>
            </label>
          </template>
        </div>
      </li>
    </ol>
  </article>
</template>
