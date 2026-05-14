<template>
  <!--
    FinanceAiBanner (Gate 8 Track C — C1).

    A dismissible warning shown at the top of finance pages that rely on
    AI features. It renders ONLY when the workspace has no LLM model
    configured — i.e. when requirement parsing / summary generation /
    document ai-fill will silently fall back to deterministic stubs.

    Dismissal is per-session (sessionStorage) so it does not nag on
    every navigation between finance list pages, but reappears on a
    fresh login / new tab.
  -->
  <el-alert
    v-if="shouldShow"
    class="finance-ai-banner"
    type="warning"
    :closable="true"
    show-icon
    @close="onDismiss"
  >
    <template #title>
      <span class="finance-ai-banner__text">
        {{ $t('views.finance.aiBanner.message') }}
      </span>
      <el-button
        link
        type="primary"
        size="small"
        class="finance-ai-banner__cta"
        @click="goConfigure"
      >
        {{ $t('views.finance.aiBanner.configureCta') }}
      </el-button>
    </template>
  </el-alert>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import useStore from '@/stores'

/**
 * Optional workspace override. When omitted the banner resolves the
 * current workspace via the user store — that is the common case for
 * the finance list pages.
 */
const props = defineProps<{
  workspaceId?: string
}>()

const router = useRouter()
const { user, financeAiStatus } = useStore()

// Per-session dismissal flag. Keyed by workspace so switching workspace
// re-shows the banner if the new one is also unconfigured.
const SESSION_KEY_PREFIX = 'finance-ai-banner-dismissed:'

const dismissed = ref(false)

const workspaceId = computed<string>(
  () => props.workspaceId || user.getWorkspaceId?.() || '',
)

const sessionKey = computed(() => SESSION_KEY_PREFIX + workspaceId.value)

const status = computed(() =>
  workspaceId.value ? financeAiStatus.statusFor(workspaceId.value) : null,
)

/**
 * Show only when: we have a status, it says the LLM is NOT configured,
 * and the user has not dismissed it this session. Fail-safe: if the
 * status fetch failed (status is null) the banner stays hidden — we
 * would rather under-warn than show a false alarm on a network blip.
 */
const shouldShow = computed<boolean>(
  () => !dismissed.value && !!status.value && status.value.llm_configured === false,
)

const onDismiss = () => {
  dismissed.value = true
  try {
    sessionStorage.setItem(sessionKey.value, '1')
  } catch {
    // sessionStorage can throw in private-mode / quota-exceeded — the
    // banner just won't persist its dismissal, which is acceptable.
  }
}

const goConfigure = () => {
  // Route name 'model' → the platform Models menu (path '/model').
  router.push({ name: 'model' }).catch(() => {
    // Navigation guards may reject (already there / no permission);
    // swallow — the CTA is best-effort convenience.
  })
}

onMounted(async () => {
  if (!workspaceId.value) return
  try {
    if (sessionStorage.getItem(sessionKey.value) === '1') {
      dismissed.value = true
    }
  } catch {
    // ignore — see onDismiss
  }
  // Fetch once; the store caches per workspace so navigating between
  // finance list pages does not re-hit the endpoint.
  await financeAiStatus.ensure(workspaceId.value)
})
</script>

<style scoped>
.finance-ai-banner {
  margin-bottom: 16px;
}
.finance-ai-banner__text {
  font-weight: 400;
}
.finance-ai-banner__cta {
  margin-left: 8px;
  vertical-align: baseline;
}
</style>
