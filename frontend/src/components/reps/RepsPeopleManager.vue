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
  <UiCard padding="lg">
    <UiSectionHeader as="h3" class="mb-4">
      People (Audit Trail)
      <template #actions>
        <span class="text-xs tabular text-fg-muted">{{ store.people.length }} contacts</span>
      </template>
    </UiSectionHeader>

    <div
      v-if="error"
      data-testid="repspeople.error"
      class="mb-3 rounded-ctl bg-negative/10 p-2 text-xs font-medium text-negative"
    >{{ error }}</div>

    <!-- Add new -->
    <div class="mb-4 grid grid-cols-1 gap-2 rounded-ctl border border-line bg-surface-muted p-3 md:grid-cols-4">
      <input
        data-testid="repspeople.new-name"
        v-model="newName"
        type="text"
        placeholder="Name *"
        class="ui-input text-sm"
        aria-label="Name"
      />
      <input
        data-testid="repspeople.new-role"
        v-model="newRole"
        type="text"
        placeholder="Role (e.g. Plumber)"
        class="ui-input text-sm"
        aria-label="Role"
      />
      <input
        data-testid="repspeople.new-notes"
        v-model="newNotes"
        type="text"
        placeholder="Notes"
        class="ui-input text-sm"
        aria-label="Notes"
      />
      <UiButton data-testid="repspeople.add" size="sm" class="min-h-9" @click="add">
        <i class="pi pi-plus" aria-hidden="true"></i> Add
      </UiButton>
    </div>

    <UiEmptyState v-if="store.people.length === 0" data-testid="repspeople.empty">
      No people yet. Add contractors, agents, lenders, etc. to tag on log entries.
    </UiEmptyState>

    <ul v-else class="divide-y divide-line">
      <li
        v-for="p in store.people"
        :key="p.id"
        :data-testid="`repspeople.person.${p.id}`"
        class="flex items-start gap-3 py-3"
      >
        <template v-if="editingId === p.id">
          <div class="grid flex-1 grid-cols-1 gap-2 md:grid-cols-3">
            <input
              :data-testid="`repspeople.person.${p.id}.edit-name`"
              v-model="editName"
              type="text"
              class="ui-input text-sm"
              aria-label="Name"
            />
            <input
              :data-testid="`repspeople.person.${p.id}.edit-role`"
              v-model="editRole"
              type="text"
              placeholder="Role"
              class="ui-input text-sm"
              aria-label="Role"
            />
            <input
              :data-testid="`repspeople.person.${p.id}.edit-notes`"
              v-model="editNotes"
              type="text"
              placeholder="Notes"
              class="ui-input text-sm"
              aria-label="Notes"
            />
          </div>
          <div class="flex shrink-0 gap-2">
            <UiIconButton
              :data-testid="`repspeople.person.${p.id}.save`"
              label="Save person"
              variant="secondary"
              @click="saveEdit"
            >
              <i class="pi pi-check" aria-hidden="true"></i>
            </UiIconButton>
            <UiIconButton
              :data-testid="`repspeople.person.${p.id}.cancel`"
              label="Cancel edit"
              @click="editingId = null"
            >
              <i class="pi pi-times" aria-hidden="true"></i>
            </UiIconButton>
          </div>
        </template>
        <template v-else>
          <div class="min-w-0 flex-1">
            <div class="break-words text-sm font-semibold text-fg">
              {{ p.name }}
              <span v-if="p.role" class="ml-1 text-xs font-normal text-fg-muted">· {{ p.role }}</span>
            </div>
            <div v-if="p.notes" class="mt-0.5 break-words text-xs text-fg-muted">{{ p.notes }}</div>
          </div>
          <div class="flex shrink-0 gap-2">
            <UiIconButton
              :data-testid="`repspeople.person.${p.id}.edit`"
              label="Edit person"
              @click="startEdit(p)"
            >
              <i class="pi pi-pencil" aria-hidden="true"></i>
            </UiIconButton>
            <UiIconButton
              :data-testid="`repspeople.person.${p.id}.delete`"
              label="Delete person"
              variant="danger"
              @click="remove(p.id)"
            >
              <i class="pi pi-trash" aria-hidden="true"></i>
            </UiIconButton>
          </div>
        </template>
      </li>
    </ul>
  </UiCard>
</template>
