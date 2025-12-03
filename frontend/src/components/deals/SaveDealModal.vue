<template>
  <Transition name="fade">
    <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur">
      <div class="card-surface w-full max-w-3xl rounded-2xl p-6">
        <div class="flex items-center justify-between mb-4">
          <p class="text-sm uppercase tracking-[0.2em] text-slate-400">Save Deal</p>
          <button class="text-slate-400 hover:text-ocean-900" @click="emitClose">✕</button>
        </div>
        <div class="grid gap-4 md:grid-cols-2">
          <label class="space-y-2">
            <p class="label-text">Section</p>
            <select v-model.number="local.section" class="input-base">
              <option :value="1">Wholesale</option>
              <option :value="2">Market</option>
              <option :value="3">Our Off Market</option>
            </select>
          </label>
          <label class="space-y-2">
            <p class="label-text">Stage</p>
            <select v-model.number="local.stage" class="input-base">
              <option :value="1">New</option>
              <option :value="2">Working</option>
              <option :value="3">Brought</option>
              <option :value="4">Keep in Mind</option>
              <option :value="5">Dead</option>
            </select>
          </label>
          <TextInput v-model="local.address" label="Address" required />
          <FieldInput v-model="local.sqft" label="Sqft" />
          <FieldInput v-model="local.bedrooms" label="Bedrooms" />
          <FieldInput v-model="local.bathrooms" label="Bathrooms" />
          <TextInput v-model="local.contact" label="Contact" />
          <TextInput v-model="local.task" label="Task" />
          <TextInput v-model="local.zillow_link" label="Zillow Link" />
          <TextInput v-model="local.pics_link" label="Pictures Link" />
          <TextInput v-model="local.crime_rate" label="Crime Rate" />
          <TextInput v-model="local.overall_design" label="Design Notes" />
          <div class="md:col-span-2 grid grid-cols-2 gap-3">
            <label class="space-y-2">
              <p class="label-text">Sold Comps (url | arv | age)</p>
              <textarea
                v-model="soldCompsText"
                class="input-base min-h-[90px]"
                placeholder="https://zillow.com/... | 350000 | 3mo"
              ></textarea>
            </label>
            <label class="space-y-2">
              <p class="label-text">Rent Comps (url | rent | days)</p>
              <textarea
                v-model="rentCompsText"
                class="input-base min-h-[90px]"
                placeholder="https://zillow.com/... | 2300 | 21d"
              ></textarea>
            </label>
          </div>
          <div class="md:col-span-2">
            <label class="label-text">Notes</label>
            <textarea
              v-model="local.notes"
              class="input-base mt-2 min-h-[120px] resize-none"
              placeholder="What makes this deal special?"
            ></textarea>
          </div>
        </div>
        <div class="mt-6 flex justify-end gap-2">
          <button class="rounded-xl bg-ocean-200/40 px-4 py-2 text-sm" @click="emitClose">Cancel</button>
          <button class="rounded-xl bg-ocean-900 px-4 py-2 text-sm font-semibold text-white shadow-glow" @click="emitSave">Save Deal</button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue';
import type { AdditionalDetails } from '../../types/deal';
import FieldInput from '../ui/FieldInput.vue';
import TextInput from '../ui/TextInput.vue';

const props = defineProps<{ open: boolean; details: AdditionalDetails }>();
const emit = defineEmits<{ (e: 'update:open', value: boolean): void; (e: 'save', value: AdditionalDetails): void }>();

const local = reactive<AdditionalDetails>({ ...props.details });
const soldCompsText = ref('');
const rentCompsText = ref('');

watch(
  () => props.details,
  (next) => {
    Object.assign(local, next);
    soldCompsText.value = (next.sold_comps || [])
      .map((c) => `${c.url} | ${c.arv} | ${c.how_long_ago}`)
      .join('\n');
    rentCompsText.value = (next.rent_comps || [])
      .map((c) => `${c.url} | ${c.rent} | ${c.time_on_market}`)
      .join('\n');
  },
  { deep: true }
);

const parseSoldComps = (value: string) =>
  value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [url, arv, age] = line.split('|').map((p) => p.trim());
      return { url, arv: Number(arv), how_long_ago: age };
    });

const parseRentComps = (value: string) =>
  value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [url, rent, days] = line.split('|').map((p) => p.trim());
      return { url, rent: Number(rent), time_on_market: days };
    });

const emitSave = () => {
  local.sold_comps = parseSoldComps(soldCompsText.value);
  local.rent_comps = parseRentComps(rentCompsText.value);
  emit('save', { ...local });
};
const emitClose = () => emit('update:open', false);
</script>
