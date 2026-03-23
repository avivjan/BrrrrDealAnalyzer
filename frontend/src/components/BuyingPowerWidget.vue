<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import type { LiquidityTransaction } from "../types";
import api from "../api";

// ── Helpers ────────────────────────────────────────────
function parseDate(d: string): Date {
  if (d.includes("T")) return new Date(d);
  return new Date(d + "T00:00:00");
}

function normalizeTxn(t: LiquidityTransaction): LiquidityTransaction {
  return { ...t, amount: Number(t.amount) };
}

// ── State ──────────────────────────────────────────────
const isOpen = ref(false);
const transactions = ref<LiquidityTransaction[]>([]);
const totalLiquidity = ref(0);
const isLoading = ref(false);

const editingId = ref<string | null>(null);
const editDraft = ref<Partial<LiquidityTransaction>>({});
const editIsInflow = ref(true);
const validationErrors = ref<Record<string, boolean>>({});

const isAddingNew = ref(false);
const newDraft = ref({ date: "", description: "", amount: 0, category: "" });
const newIsInflow = ref(true);
const newValidationErrors = ref<Record<string, boolean>>({});

const categorySearch = ref("");
const showCategoryDropdown = ref(false);
const categoryInputRef = ref<HTMLInputElement | null>(null);
const newCategorySearch = ref("");
const showNewCategoryDropdown = ref(false);
const newCategoryInputRef = ref<HTMLInputElement | null>(null);

const pendingDeletes = ref<Map<string, ReturnType<typeof setTimeout>>>(
  new Map(),
);
const undoToasts = ref<{ id: string; description: string; timer: number }[]>(
  [],
);

// ── Derived ────────────────────────────────────────────
const DEFAULT_CATEGORIES = [
  "cashoutrefi",
  "cashflow",
  "flip profit",
  "flip purchase",
  "rental purchase",
];

const existingCategories = computed(() => {
  const cats = new Set(DEFAULT_CATEGORIES);
  transactions.value.forEach((t) => {
    if (t.category) cats.add(t.category);
  });
  return Array.from(cats).sort();
});

const filteredCategories = computed(() => {
  const q = categorySearch.value.toLowerCase().trim();
  if (!q) return existingCategories.value;
  return existingCategories.value.filter((c) => c.toLowerCase().includes(q));
});

const showAddCategory = computed(() => {
  const q = categorySearch.value.trim();
  return (
    q.length > 0 &&
    !existingCategories.value.some((c) => c.toLowerCase() === q.toLowerCase())
  );
});

const filteredNewCategories = computed(() => {
  const q = newCategorySearch.value.toLowerCase().trim();
  if (!q) return existingCategories.value;
  return existingCategories.value.filter((c) => c.toLowerCase().includes(q));
});

const showAddNewCategory = computed(() => {
  const q = newCategorySearch.value.trim();
  return (
    q.length > 0 &&
    !existingCategories.value.some((c) => c.toLowerCase() === q.toLowerCase())
  );
});

const visibleTransactions = computed(() =>
  transactions.value
    .filter((t) => !pendingDeletes.value.has(t.id))
    .sort((a, b) => parseDate(b.date).getTime() - parseDate(a.date).getTime()),
);

const sparklinePoints = computed(() => {
  if (transactions.value.length === 0) return "";
  const sorted = [...transactions.value].sort(
    (a, b) => parseDate(a.date).getTime() - parseDate(b.date).getTime(),
  );

  const sixMonthsAgo = new Date();
  sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 6);
  const recent = sorted.filter((t) => parseDate(t.date) >= sixMonthsAgo);
  const data = recent.length > 0 ? recent : sorted.slice(-12);

  if (data.length === 0) return "";

  let running = 0;
  const points: { x: number; y: number }[] = [];
  data.forEach((t, i) => {
    running += t.amount;
    points.push({ x: i, y: running });
  });

  const maxX = points.length - 1 || 1;
  const minY = Math.min(...points.map((p) => p.y));
  const maxY = Math.max(...points.map((p) => p.y));
  const rangeY = maxY - minY || 1;

  const w = 80;
  const h = 28;
  const pad = 2;

  return points
    .map((p) => {
      const x = pad + (p.x / maxX) * (w - pad * 2);
      const y = h - pad - ((p.y - minY) / rangeY) * (h - pad * 2);
      return `${x},${y}`;
    })
    .join(" ");
});

const sparklineGradientPoints = computed(() => {
  if (!sparklinePoints.value) return "";
  const pts = sparklinePoints.value.split(" ");
  const firstX = pts[0]?.split(",")[0] ?? "2";
  const lastX = pts[pts.length - 1]?.split(",")[0] ?? "78";
  return `${firstX},30 ${sparklinePoints.value} ${lastX},30`;
});

// ── API calls ──────────────────────────────────────────
async function fetchLiquidity() {
  isLoading.value = true;
  try {
    const res = await api.getLiquidity();
    transactions.value = res.transactions.map(normalizeTxn);
    totalLiquidity.value = Number(res.total_liquidity);
  } catch {
    console.warn("Liquidity API not available yet");
  } finally {
    isLoading.value = false;
  }
}

async function saveTransaction(txn: LiquidityTransaction) {
  try {
    const updated = normalizeTxn(await api.updateLiquidityTransaction(txn));
    const idx = transactions.value.findIndex((t) => t.id === txn.id);
    if (idx !== -1) transactions.value[idx] = updated;
    await refreshTotal();
  } catch {
    console.warn("Update API not available yet");
  }
}

async function createTransaction(data: Omit<LiquidityTransaction, "id">) {
  try {
    const created = normalizeTxn(await api.addLiquidityTransaction(data));
    transactions.value.push(created);
    await refreshTotal();
  } catch {
    console.warn("Create API not available yet");
  }
}

async function deleteTransaction(id: string) {
  try {
    await api.deleteLiquidityTransaction(id);
    transactions.value = transactions.value.filter((t) => t.id !== id);
    await refreshTotal();
  } catch {
    console.warn("Delete API not available yet");
  }
}

async function refreshTotal() {
  try {
    const res = await api.getLiquidity();
    totalLiquidity.value = Number(res.total_liquidity);
  } catch {
    // fallback: compute locally
    totalLiquidity.value = transactions.value.reduce(
      (sum, t) => sum + t.amount,
      0,
    );
  }
}

// ── Edit logic ─────────────────────────────────────────
function startEdit(txn: LiquidityTransaction) {
  editingId.value = txn.id;
  editIsInflow.value = txn.amount >= 0;
  editDraft.value = { ...txn, amount: Math.abs(txn.amount) };
  categorySearch.value = txn.category;
  validationErrors.value = {};
}

function validateDraft(): boolean {
  const errors: Record<string, boolean> = {};
  if (!editDraft.value.date) errors.date = true;
  if (!editDraft.value.description?.trim()) errors.description = true;
  if (
    editDraft.value.amount === undefined ||
    editDraft.value.amount === null ||
    isNaN(Number(editDraft.value.amount))
  )
    errors.amount = true;
  if (!categorySearch.value.trim()) errors.category = true;
  validationErrors.value = errors;
  return Object.keys(errors).length === 0;
}

function commitEdit() {
  if (!editingId.value) return;
  editDraft.value.category = categorySearch.value.trim();
  if (!validateDraft()) return;

  editDraft.value.amount =
    Math.abs(editDraft.value.amount ?? 0) * (editIsInflow.value ? 1 : -1);

  const txn = transactions.value.find((t) => t.id === editingId.value);
  if (txn) {
    Object.assign(txn, editDraft.value);
    saveTransaction({ ...txn });
  }
  editingId.value = null;
  editDraft.value = {};
  categorySearch.value = "";
  showCategoryDropdown.value = false;
}

function handleEditBlur(e: FocusEvent) {
  const related = e.relatedTarget as HTMLElement | null;
  const row = (e.currentTarget as HTMLElement)?.closest("[data-edit-row]");
  if (row && related && row.contains(related)) return;
  // Small delay to allow dropdown clicks to register
  setTimeout(() => {
    if (editingId.value) commitEdit();
  }, 150);
}

// ── New transaction logic ──────────────────────────────
function startAddNew() {
  isAddingNew.value = true;
  newIsInflow.value = true;
  const today = new Date().toISOString().split("T")[0] ?? "";
  newDraft.value = { date: today, description: "", amount: 0, category: "" };
  newCategorySearch.value = "";
  newValidationErrors.value = {};
}

function validateNewDraft(): boolean {
  const errors: Record<string, boolean> = {};
  if (!newDraft.value.date) errors.date = true;
  if (!newDraft.value.description?.trim()) errors.description = true;
  if (isNaN(Number(newDraft.value.amount))) errors.amount = true;
  if (!newCategorySearch.value.trim()) errors.category = true;
  newValidationErrors.value = errors;
  return Object.keys(errors).length === 0;
}

function commitNew() {
  newDraft.value.category = newCategorySearch.value.trim();
  if (!validateNewDraft()) return;
  const amount = Math.abs(newDraft.value.amount) * (newIsInflow.value ? 1 : -1);
  createTransaction({ ...newDraft.value, amount });
  isAddingNew.value = false;
  newDraft.value = { date: "", description: "", amount: 0, category: "" };
  newCategorySearch.value = "";
}

function cancelNew() {
  isAddingNew.value = false;
  newValidationErrors.value = {};
}

function handleNewBlur(e: FocusEvent) {
  const related = e.relatedTarget as HTMLElement | null;
  const row = (e.currentTarget as HTMLElement)?.closest("[data-new-row]");
  if (row && related && row.contains(related)) return;
  setTimeout(() => {
    if (isAddingNew.value) {
      if (
        newDraft.value.description?.trim() ||
        newDraft.value.amount ||
        newCategorySearch.value.trim()
      ) {
        commitNew();
      } else {
        cancelNew();
      }
    }
  }, 150);
}

// ── Category combobox ──────────────────────────────────
function selectCategory(cat: string) {
  categorySearch.value = cat;
  showCategoryDropdown.value = false;
  if (editDraft.value) editDraft.value.category = cat;
}

function selectNewCategory(cat: string) {
  newCategorySearch.value = cat;
  showNewCategoryDropdown.value = false;
  newDraft.value.category = cat;
}

function handleCategoryDropdownBlur() {
  setTimeout(() => {
    showCategoryDropdown.value = false;
  }, 150);
}

function handleNewCategoryDropdownBlur() {
  setTimeout(() => {
    showNewCategoryDropdown.value = false;
  }, 150);
}

// ── Delete + Undo ──────────────────────────────────────
function requestDelete(txn: LiquidityTransaction) {
  const timer = setTimeout(() => {
    pendingDeletes.value.delete(txn.id);
    undoToasts.value = undoToasts.value.filter((t) => t.id !== txn.id);
    deleteTransaction(txn.id);
  }, 5000);

  pendingDeletes.value.set(txn.id, timer);
  undoToasts.value.push({
    id: txn.id,
    description: txn.description || "Transaction",
    timer: Date.now() + 5000,
  });
}

function undoDelete(id: string) {
  const timer = pendingDeletes.value.get(id);
  if (timer) clearTimeout(timer);
  pendingDeletes.value.delete(id);
  undoToasts.value = undoToasts.value.filter((t) => t.id !== id);
}

// ── Widget toggle ──────────────────────────────────────
function togglePopup() {
  isOpen.value = !isOpen.value;
  if (isOpen.value) {
    fetchLiquidity();
  }
}

function closePopup() {
  if (editingId.value) commitEdit();
  if (isAddingNew.value) cancelNew();
  isOpen.value = false;
}

// ── Format helpers ─────────────────────────────────────
function formatAmount(val: number): string {
  const abs = Math.abs(val);
  const formatted =
    abs >= 1
      ? `$${abs.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 1 })}k`
      : `$${(abs * 1000).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
  return val < 0 ? `-${formatted}` : formatted;
}

function formatDate(d: string): string {
  if (!d) return "";
  const dt = parseDate(d);
  if (isNaN(dt.getTime())) return "";
  return dt.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "2-digit",
  });
}

function categoryLabel(cat: string): string {
  return cat
    .replace(/([A-Z])/g, " $1")
    .replace(/[-_]/g, " ")
    .trim();
}

// ── Lifecycle ──────────────────────────────────────────
onMounted(() => {
  fetchLiquidity();
});

onUnmounted(() => {
  pendingDeletes.value.forEach((timer) => clearTimeout(timer));
});
</script>

<template>
  <!-- Floating Widget -->
  <div class="fixed bottom-3 right-3 sm:bottom-5 sm:right-5 z-40">
    <button
      @click="togglePopup"
      class="group relative flex items-center gap-2 sm:gap-3 px-3 py-2 sm:px-5 sm:py-3 rounded-2xl shadow-lg border border-white/40 transition-all duration-300 hover:shadow-xl hover:scale-105 active:scale-95 cursor-pointer"
      :class="
        isOpen
          ? 'bg-white/90 backdrop-blur-xl shadow-blue-200/50'
          : 'bg-white/70 backdrop-blur-xl hover:bg-white/85'
      "
    >
      <div class="flex flex-col items-start">
        <span
          class="text-[10px] font-semibold uppercase tracking-wider text-gray-400"
        >
          Buying Power
        </span>
        <span
          class="text-base sm:text-xl font-bold tracking-tight"
          :class="totalLiquidity >= 0 ? 'text-emerald-600' : 'text-red-500'"
        >
          {{ formatAmount(totalLiquidity) }}
        </span>
      </div>

      <!-- Sparkline -->
      <svg
        v-if="sparklinePoints"
        width="80"
        height="30"
        class="flex-shrink-0 opacity-60 group-hover:opacity-100 transition-opacity"
      >
        <defs>
          <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
            <stop
              offset="0%"
              :stop-color="totalLiquidity >= 0 ? '#10b981' : '#ef4444'"
              stop-opacity="0.3"
            />
            <stop
              offset="100%"
              :stop-color="totalLiquidity >= 0 ? '#10b981' : '#ef4444'"
              stop-opacity="0"
            />
          </linearGradient>
        </defs>
        <polygon
          v-if="sparklineGradientPoints"
          :points="sparklineGradientPoints"
          fill="url(#sparkFill)"
        />
        <polyline
          :points="sparklinePoints"
          fill="none"
          :stroke="totalLiquidity >= 0 ? '#10b981' : '#ef4444'"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>

      <i
        class="pi pi-chevron-up text-xs text-gray-400 transition-transform duration-300"
        :class="{ 'rotate-180': isOpen }"
      ></i>
    </button>
  </div>

  <!-- Popup Overlay -->
  <Transition name="popup">
    <div
      v-if="isOpen"
      class="fixed z-50 flex flex-col shadow-2xl border border-gray-200/60 bg-white/95 backdrop-blur-2xl overflow-hidden inset-0 sm:inset-auto sm:bottom-20 sm:right-5 sm:w-[480px] sm:max-h-[70vh] sm:rounded-2xl"
    >
      <!-- Header -->
      <div
        class="flex items-center justify-between px-4 py-3 sm:px-5 sm:py-4 pt-[max(0.75rem,env(safe-area-inset-top))] border-b border-gray-100 bg-gradient-to-r from-gray-50/80 to-white/80"
      >
        <div>
          <h3 class="text-base font-bold text-gray-900 tracking-tight">
            Liquidity Transactions
          </h3>
          <p class="text-xs text-gray-400 mt-0.5">
            Total:
            <span
              class="font-bold"
              :class="totalLiquidity >= 0 ? 'text-emerald-600' : 'text-red-500'"
            >
              {{ formatAmount(totalLiquidity) }}
            </span>
          </p>
        </div>
        <div class="flex items-center gap-2">
          <button
            @click="startAddNew"
            class="w-8 h-8 flex items-center justify-center rounded-full bg-blue-50 text-blue-600 hover:bg-blue-100 hover:scale-110 transition-all"
            title="Add Transaction"
          >
            <i class="pi pi-plus text-sm font-bold"></i>
          </button>
          <button
            @click="closePopup"
            class="w-8 h-8 flex items-center justify-center rounded-full bg-gray-100 text-gray-500 hover:bg-gray-200 hover:scale-110 transition-all"
          >
            <i class="pi pi-times text-xs"></i>
          </button>
        </div>
      </div>

      <!-- Transaction List -->
      <div class="flex-1 overflow-y-auto px-2 py-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] space-y-1">
        <!-- New Transaction Row -->
        <div
          v-if="isAddingNew"
          data-new-row
          class="bg-blue-50/60 border border-blue-200/60 rounded-xl p-3 space-y-2 animate-in"
        >
          <div class="grid grid-cols-[100px_1fr] gap-2">
            <input
              v-model="newDraft.date"
              type="date"
              class="text-xs bg-white border rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400 transition-all"
              :class="
                newValidationErrors.date
                  ? 'border-red-400 ring-1 ring-red-300'
                  : 'border-gray-200'
              "
              @blur="handleNewBlur"
            />
            <input
              v-model="newDraft.description"
              type="text"
              placeholder="Description"
              class="text-xs bg-white border rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400 transition-all"
              :class="
                newValidationErrors.description
                  ? 'border-red-400 ring-1 ring-red-300'
                  : 'border-gray-200'
              "
              @blur="handleNewBlur"
            />
          </div>
          <div class="flex items-center gap-2">
            <button
              type="button"
              @mousedown.prevent="newIsInflow = !newIsInflow"
              class="flex-shrink-0 w-16 h-7 rounded-lg text-[11px] font-bold transition-all border"
              :class="
                newIsInflow
                  ? 'bg-emerald-50 text-emerald-600 border-emerald-200 hover:bg-emerald-100'
                  : 'bg-red-50 text-red-500 border-red-200 hover:bg-red-100'
              "
            >
              {{ newIsInflow ? "+ In" : "− Out" }}
            </button>
            <input
              v-model.number="newDraft.amount"
              type="number"
              step="0.1"
              min="0"
              placeholder="$000s"
              class="flex-1 text-xs bg-white border rounded-lg px-2 py-1.5 text-right font-mono focus:outline-none focus:ring-2 focus:ring-blue-400 transition-all"
              :class="
                newValidationErrors.amount
                  ? 'border-red-400 ring-1 ring-red-300'
                  : 'border-gray-200'
              "
              @blur="handleNewBlur"
            />
          </div>
          <div class="flex items-center gap-2">
            <!-- Category Combobox (New) -->
            <div class="relative flex-1">
              <input
                ref="newCategoryInputRef"
                v-model="newCategorySearch"
                type="text"
                placeholder="Category"
                class="w-full text-xs bg-white border rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400 transition-all"
                :class="
                  newValidationErrors.category
                    ? 'border-red-400 ring-1 ring-red-300'
                    : 'border-gray-200'
                "
                @focus="showNewCategoryDropdown = true"
                @blur="
                  (e: FocusEvent) => {
                    handleNewCategoryDropdownBlur();
                    handleNewBlur(e);
                  }
                "
              />
              <div
                v-if="showNewCategoryDropdown"
                class="absolute bottom-full left-0 right-0 mb-1 bg-white border border-gray-200 rounded-lg shadow-lg z-10 max-h-40 overflow-y-auto"
              >
                <button
                  v-if="showAddNewCategory"
                  @mousedown.prevent="
                    selectNewCategory(newCategorySearch.trim())
                  "
                  class="w-full text-left px-3 py-1.5 text-xs text-blue-600 font-medium hover:bg-blue-50 flex items-center gap-1.5"
                >
                  <i class="pi pi-plus-circle text-[10px]"></i>
                  Add "{{ newCategorySearch.trim() }}"
                </button>
                <button
                  v-for="cat in filteredNewCategories"
                  :key="cat"
                  @mousedown.prevent="selectNewCategory(cat)"
                  class="w-full text-left px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 capitalize"
                >
                  {{ categoryLabel(cat) }}
                </button>
              </div>
            </div>
            <button
              @mousedown.prevent="commitNew"
              class="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-lg hover:bg-blue-700 transition-colors font-medium"
            >
              Add
            </button>
            <button
              @mousedown.prevent="cancelNew"
              class="px-3 py-1.5 bg-gray-100 text-gray-600 text-xs rounded-lg hover:bg-gray-200 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>

        <!-- Loading state -->
        <div
          v-if="isLoading && transactions.length === 0"
          class="flex items-center justify-center py-12 text-gray-400"
        >
          <i class="pi pi-spin pi-spinner text-xl mr-2"></i>
          <span class="text-sm">Loading...</span>
        </div>

        <!-- Empty state -->
        <div
          v-else-if="visibleTransactions.length === 0 && !isAddingNew"
          class="flex flex-col items-center justify-center py-12 text-gray-400"
        >
          <i class="pi pi-wallet text-3xl mb-2 opacity-40"></i>
          <p class="text-sm">No transactions yet</p>
          <button
            @click="startAddNew"
            class="mt-3 text-xs text-blue-600 hover:text-blue-800 font-medium"
          >
            Add your first transaction
          </button>
        </div>

        <!-- Transaction rows -->
        <div
          v-for="txn in visibleTransactions"
          :key="txn.id"
          :data-edit-row="editingId === txn.id ? true : undefined"
          class="group rounded-xl px-3 py-2.5 transition-all duration-200 hover:bg-gray-50/80"
          :class="
            editingId === txn.id
              ? 'bg-amber-50/50 border border-amber-200/50'
              : ''
          "
        >
          <!-- Display Mode -->
          <div v-if="editingId !== txn.id" class="flex items-center gap-3">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="text-xs text-gray-400 font-mono whitespace-nowrap">
                  {{ formatDate(txn.date) }}
                </span>
                <span class="text-sm text-gray-800 font-medium truncate">
                  {{ txn.description }}
                </span>
              </div>
              <span
                class="text-[10px] uppercase tracking-wider font-semibold mt-0.5 inline-block px-1.5 py-0.5 rounded-md"
                :class="
                  txn.amount >= 0
                    ? 'text-emerald-600 bg-emerald-50'
                    : 'text-red-500 bg-red-50'
                "
              >
                {{ categoryLabel(txn.category) }}
              </span>
            </div>

            <span
              class="text-sm font-bold font-mono tabular-nums whitespace-nowrap"
              :class="txn.amount >= 0 ? 'text-emerald-600' : 'text-red-500'"
            >
              {{ txn.amount >= 0 ? "+" : "" }}{{ formatAmount(txn.amount) }}
            </span>

            <!-- Actions -->
            <div
              class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <button
                @click="startEdit(txn)"
                class="w-6 h-6 flex items-center justify-center rounded-full hover:bg-gray-200 text-gray-400 hover:text-gray-600 transition-all"
                title="Edit"
              >
                <i class="pi pi-pencil text-[10px]"></i>
              </button>
              <button
                @click="requestDelete(txn)"
                class="w-6 h-6 flex items-center justify-center rounded-full hover:bg-red-100 text-gray-400 hover:text-red-500 transition-all"
                title="Delete"
              >
                <i class="pi pi-times text-[10px]"></i>
              </button>
            </div>
          </div>

          <!-- Edit Mode -->
          <div v-else class="space-y-2">
            <div class="grid grid-cols-[100px_1fr] gap-2">
              <input
                v-model="editDraft.date"
                type="date"
                class="text-xs bg-white border rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-amber-400 transition-all"
                :class="
                  validationErrors.date
                    ? 'border-red-400 ring-1 ring-red-300'
                    : 'border-gray-200'
                "
                @blur="handleEditBlur"
              />
              <input
                v-model="editDraft.description"
                type="text"
                class="text-xs bg-white border rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-amber-400 transition-all"
                :class="
                  validationErrors.description
                    ? 'border-red-400 ring-1 ring-red-300'
                    : 'border-gray-200'
                "
                @blur="handleEditBlur"
              />
            </div>
            <div class="flex items-center gap-2">
              <button
                type="button"
                @mousedown.prevent="editIsInflow = !editIsInflow"
                class="flex-shrink-0 w-16 h-7 rounded-lg text-[11px] font-bold transition-all border"
                :class="
                  editIsInflow
                    ? 'bg-emerald-50 text-emerald-600 border-emerald-200 hover:bg-emerald-100'
                    : 'bg-red-50 text-red-500 border-red-200 hover:bg-red-100'
                "
              >
                {{ editIsInflow ? "+ In" : "− Out" }}
              </button>
              <input
                v-model.number="editDraft.amount"
                type="number"
                step="0.1"
                min="0"
                class="flex-1 text-xs bg-white border rounded-lg px-2 py-1.5 text-right font-mono focus:outline-none focus:ring-2 focus:ring-amber-400 transition-all"
                :class="
                  validationErrors.amount
                    ? 'border-red-400 ring-1 ring-red-300'
                    : 'border-gray-200'
                "
                @blur="handleEditBlur"
              />
            </div>
            <!-- Category Combobox (Edit) -->
            <div class="relative">
              <input
                ref="categoryInputRef"
                v-model="categorySearch"
                type="text"
                placeholder="Category"
                class="w-full text-xs bg-white border rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-amber-400 transition-all capitalize"
                :class="
                  validationErrors.category
                    ? 'border-red-400 ring-1 ring-red-300'
                    : 'border-gray-200'
                "
                @focus="showCategoryDropdown = true"
                @blur="
                  (e: FocusEvent) => {
                    handleCategoryDropdownBlur();
                    handleEditBlur(e);
                  }
                "
              />
              <div
                v-if="showCategoryDropdown"
                class="absolute bottom-full left-0 right-0 mb-1 bg-white border border-gray-200 rounded-lg shadow-lg z-10 max-h-40 overflow-y-auto"
              >
                <button
                  v-if="showAddCategory"
                  @mousedown.prevent="selectCategory(categorySearch.trim())"
                  class="w-full text-left px-3 py-1.5 text-xs text-blue-600 font-medium hover:bg-blue-50 flex items-center gap-1.5"
                >
                  <i class="pi pi-plus-circle text-[10px]"></i>
                  Add "{{ categorySearch.trim() }}"
                </button>
                <button
                  v-for="cat in filteredCategories"
                  :key="cat"
                  @mousedown.prevent="selectCategory(cat)"
                  class="w-full text-left px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 capitalize"
                >
                  {{ categoryLabel(cat) }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>

  <!-- Undo Toasts -->
  <TransitionGroup
    name="toast"
    tag="div"
    class="fixed bottom-16 left-3 right-3 sm:bottom-5 sm:left-5 sm:right-auto z-[60] space-y-2"
  >
    <div
      v-for="toast in undoToasts"
      :key="toast.id"
      class="flex items-center gap-3 px-4 py-3 bg-gray-900 text-white rounded-xl shadow-xl text-sm"
    >
      <i class="pi pi-trash text-xs opacity-60"></i>
      <span class="truncate max-w-[200px]">
        "{{ toast.description }}" deleted
      </span>
      <button
        @click="undoDelete(toast.id)"
        class="px-2.5 py-1 bg-white/15 rounded-lg text-xs font-semibold hover:bg-white/25 transition-colors whitespace-nowrap"
      >
        Undo
      </button>
    </div>
  </TransitionGroup>
</template>

<style scoped>
.popup-enter-active,
.popup-leave-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.popup-enter-from {
  opacity: 0;
  transform: translateY(12px) scale(0.96);
}
.popup-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.98);
}

.toast-enter-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.toast-leave-active {
  transition: all 0.2s ease-in;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(-20px) scale(0.95);
}
.toast-move {
  transition: transform 0.3s ease;
}

.animate-in {
  animation: slideIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
