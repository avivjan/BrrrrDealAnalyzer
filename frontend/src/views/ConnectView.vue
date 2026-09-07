<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { authApi, type OAuthTxn } from "../api/auth";
import { useAuthStore } from "../stores/authStore";

/**
 * MCP connector consent (SECURITY_PLAN.md §3.6). claude.ai / Claude Code
 * arrive here from the API's /authorize with `?txn=`; a trusted passkey
 * session approves, which registers the connector as a device and sends the
 * browser back to the connector with its authorization code.
 */
const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

const txn = typeof route.query.txn === "string" ? route.query.txn : "";
const info = ref<OAuthTxn | null>(null);
const error = ref<string | null>(null);
const busy = ref(false);
const done = ref(false);

function describe(e: any): string {
  return e?.response?.data?.detail || e?.message || "Something went wrong";
}

async function approve() {
  busy.value = true;
  error.value = null;
  try {
    let result: { redirect_uri: string };
    try {
      result = await authApi.oauthApprove(txn);
    } catch (e: any) {
      if (e?.response?.data?.detail !== "reauth_required") throw e;
      await auth.reauth(); // step-up: confirm with the passkey, then retry
      result = await authApi.oauthApprove(txn);
    }
    done.value = true;
    window.location.assign(result.redirect_uri);
  } catch (e) {
    error.value = describe(e);
  } finally {
    busy.value = false;
  }
}

onMounted(async () => {
  if (!txn) {
    error.value = "This link is missing its transaction id.";
    return;
  }
  if (auth.status === "unknown") await auth.load();
  if (auth.status !== "trusted") {
    await router.replace({ name: "login", query: { next: route.fullPath } });
    return;
  }
  try {
    info.value = await authApi.oauthTxn(txn);
  } catch (e) {
    error.value = describe(e);
  }
});
</script>

<template>
  <section class="mx-auto flex min-h-[60vh] max-w-md flex-col justify-center gap-6 p-6" data-testid="connect.page">
    <div>
      <p class="text-xs uppercase tracking-wide text-fg-muted">BigWhales</p>
      <h1 class="text-2xl font-semibold text-fg">Connect an assistant</h1>
    </div>

    <template v-if="info">
      <p class="text-sm text-fg" data-testid="connect.client">
        <strong>{{ info.client_name }}</strong> wants to use the Big Whales tools as
        <strong>{{ auth.user?.display_name }}</strong>: deals, liquidity, the REPS log and sending offers.
      </p>
      <p class="text-xs text-fg-muted">
        It becomes a device on your account. You can revoke it at any time; it never sees your bank tokens.
      </p>
      <div class="flex gap-3">
        <button
          type="button"
          data-testid="connect.approve"
          :disabled="busy || done"
          class="flex-1 rounded-ctl bg-primary px-4 py-3 font-medium text-primary-fg disabled:opacity-60"
          @click="approve"
        >
          <i class="pi pi-check mr-2" aria-hidden="true"></i>{{ busy ? "Confirming…" : "Allow" }}
        </button>
        <RouterLink to="/" class="flex-1 rounded-ctl border border-line px-4 py-3 text-center font-medium text-fg" data-testid="connect.cancel">
          Cancel
        </RouterLink>
      </div>
    </template>

    <p v-if="error" class="text-sm text-negative" role="alert" data-testid="connect.error">{{ error }}</p>
  </section>
</template>
