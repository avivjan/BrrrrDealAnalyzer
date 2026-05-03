<script setup lang="ts">
import { ref } from 'vue';
import { useRepsStore } from '../../stores/repsStore';

const store = useRepsStore();

const newName = ref('');
const newRole = ref('');
const newNotes = ref('');
const editingId = ref<string | null>(null);
const editName = ref('');
const editRole = ref('');
const editNotes = ref('');
const error = ref('');

async function add() {
  error.value = '';
  if (!newName.value.trim()) return;
  try {
    await store.addPerson({
      name: newName.value.trim(),
      role: newRole.value.trim() || undefined,
      notes: newNotes.value.trim() || undefined,
    });
    newName.value = '';
    newRole.value = '';
    newNotes.value = '';
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Failed to add';
  }
}

function startEdit(p: { id: string; name: string; role?: string | null; notes?: string | null }) {
  editingId.value = p.id;
  editName.value = p.name;
  editRole.value = p.role || '';
  editNotes.value = p.notes || '';
}

async function saveEdit() {
  if (!editingId.value) return;
  error.value = '';
  try {
    await store.updatePerson(editingId.value, {
      name: editName.value.trim(),
      role: editRole.value.trim() || undefined,
      notes: editNotes.value.trim() || undefined,
    });
    editingId.value = null;
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Failed to update';
  }
}

async function remove(id: string) {
  if (!confirm('Delete this person? Existing log entries will keep the name.')) return;
  try {
    await store.removePerson(id);
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Failed to delete';
  }
}
</script>

<template>
  <div class="rounded-2xl border border-slate-200 bg-white shadow-sm p-6">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-bold text-slate-800">People (Audit Trail)</h3>
      <span class="text-xs font-mono text-slate-500">{{ store.people.length }} contacts</span>
    </div>

    <div v-if="error" class="p-2 mb-3 bg-rose-100 text-rose-700 text-xs rounded">{{ error }}</div>

    <!-- Add new -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-2 mb-4 p-3 rounded-lg bg-slate-50 border border-slate-100">
      <input
        v-model="newName"
        type="text"
        placeholder="Name *"
        class="px-3 py-1.5 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
      />
      <input
        v-model="newRole"
        type="text"
        placeholder="Role (e.g. Plumber)"
        class="px-3 py-1.5 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
      />
      <input
        v-model="newNotes"
        type="text"
        placeholder="Notes"
        class="px-3 py-1.5 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
      />
      <button
        class="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium flex items-center justify-center gap-2"
        @click="add"
      >
        <i class="pi pi-plus"></i> Add
      </button>
    </div>

    <div v-if="store.people.length === 0" class="text-center text-sm text-slate-500 py-6">
      No people yet. Add contractors, agents, lenders, etc. to tag on log entries.
    </div>

    <ul v-else class="divide-y divide-slate-100">
      <li
        v-for="p in store.people"
        :key="p.id"
        class="py-3 flex items-start gap-3"
      >
        <template v-if="editingId === p.id">
          <div class="flex-1 grid grid-cols-1 md:grid-cols-3 gap-2">
            <input
              v-model="editName"
              type="text"
              class="px-3 py-1.5 text-sm border border-slate-300 rounded-lg"
            />
            <input
              v-model="editRole"
              type="text"
              placeholder="Role"
              class="px-3 py-1.5 text-sm border border-slate-300 rounded-lg"
            />
            <input
              v-model="editNotes"
              type="text"
              placeholder="Notes"
              class="px-3 py-1.5 text-sm border border-slate-300 rounded-lg"
            />
          </div>
          <div class="flex gap-1 shrink-0">
            <button
              class="px-2 py-1 text-xs bg-emerald-100 text-emerald-700 rounded hover:bg-emerald-200"
              @click="saveEdit"
            >
              <i class="pi pi-check"></i>
            </button>
            <button
              class="px-2 py-1 text-xs bg-slate-100 text-slate-700 rounded hover:bg-slate-200"
              @click="editingId = null"
            >
              <i class="pi pi-times"></i>
            </button>
          </div>
        </template>
        <template v-else>
          <div class="flex-1">
            <div class="text-sm font-semibold text-slate-800">
              {{ p.name }}
              <span v-if="p.role" class="text-xs font-normal text-slate-500 ml-1">· {{ p.role }}</span>
            </div>
            <div v-if="p.notes" class="text-xs text-slate-500 mt-0.5">{{ p.notes }}</div>
          </div>
          <div class="flex gap-1 shrink-0">
            <button
              class="px-2 py-1 text-xs bg-slate-100 text-slate-700 rounded hover:bg-slate-200"
              @click="startEdit(p)"
            >
              <i class="pi pi-pencil"></i>
            </button>
            <button
              class="px-2 py-1 text-xs bg-rose-100 text-rose-700 rounded hover:bg-rose-200"
              @click="remove(p.id)"
            >
              <i class="pi pi-trash"></i>
            </button>
          </div>
        </template>
      </li>
    </ul>
  </div>
</template>
