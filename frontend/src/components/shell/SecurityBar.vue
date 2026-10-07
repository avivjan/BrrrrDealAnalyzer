<script setup lang="ts">
import { computed, watch } from "vue";
import { useAuthStore } from "../../stores/authStore";
import { useMemberLoanStore } from "../../stores/memberLoanStore";

/**
 * A one-line strip above every page, only while a session exists: who is
 * signed in, the way to the devices dashboard and, for the two members of the
 * Member Loan only, the way to the loan with how many changes wait for them.
 * With `AUTH_MODE=off` there is no session, so nothing renders, nothing is
 * requested, and every page is exactly as before.
 */
const auth = useAuthStore();
const memberLoan = useMemberLoanStore();
const shown = computed(() => auth.status === "trusted" || auth.status === "pending");

watch(
  () => auth.status,
  (status) => {
    if (status === "trusted" && !memberLoan.access) void memberLoan.loadAccess();
  },
  { immediate: true },
);
</script>

<template>
  <div
    v-if="shown"
    class="flex items-center justify-between gap-3 border-b border-line bg-surface px-4 py-1.5 text-xs text-fg-muted"
    data-testid="security.bar"
  >
    <span>Signed in as <strong class="text-fg">{{ auth.user?.display_name }}</strong></span>
    <span class="flex items-center gap-4">
      <RouterLink v-if="memberLoan.access?.allowed" to="/member-loan" class="text-primary underline-offset-2 hover:underline" data-testid="security.member-loan-link">
        <i class="pi pi-briefcase mr-1" aria-hidden="true"></i>Member Loan<span
          v-if="memberLoan.access.proposals_waiting_for_you"
          class="ml-1 rounded-full bg-primary px-1.5 text-[11px] text-primary-fg"
          :aria-label="`${memberLoan.access.proposals_waiting_for_you} waiting for you`"
        >{{ memberLoan.access.proposals_waiting_for_you }}</span>
      </RouterLink>
      <RouterLink to="/settings/devices" class="text-primary underline-offset-2 hover:underline" data-testid="security.devices-link">
        <i class="pi pi-shield mr-1" aria-hidden="true"></i>Devices &amp; passkeys
      </RouterLink>
    </span>
  </div>
</template>
