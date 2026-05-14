import { defineStore } from 'pinia'
import { getFinanceAiStatus, type FinanceAiStatus } from '@/api/finance/ai-status'

/**
 * Finance AI-status store (Gate 8 Track C).
 *
 * A tiny cache so the FinanceAiBanner does not re-hit `/ai-status` on
 * every navigation between finance list pages. The status is per
 * workspace and changes rarely (only when an admin (de)configures a
 * model), so caching it for the lifetime of the SPA session is fine —
 * `refresh()` lets callers force a re-fetch if needed.
 */
export interface FinanceAiStatusState {
  /** Cached status keyed by workspace id. */
  byWorkspace: Record<string, FinanceAiStatus>
  /** In-flight fetch guard, keyed by workspace id. */
  loading: Record<string, boolean>
}

const useFinanceAiStatusStore = defineStore('finance-ai-status', {
  state: (): FinanceAiStatusState => ({
    byWorkspace: {},
    loading: {},
  }),
  getters: {
    /** Returns the cached status for a workspace, or null if not fetched. */
    statusFor:
      (state) =>
      (workspaceId: string): FinanceAiStatus | null =>
        state.byWorkspace[workspaceId] ?? null,
  },
  actions: {
    /**
     * Fetch the AI status for a workspace, using the cache when present.
     * Pass `force` to bypass the cache. Never throws — on failure the
     * status is simply left absent (banner stays hidden, fail-safe).
     */
    async ensure(workspaceId: string, force = false): Promise<FinanceAiStatus | null> {
      if (!workspaceId) return null
      if (!force && this.byWorkspace[workspaceId]) {
        return this.byWorkspace[workspaceId]
      }
      if (this.loading[workspaceId]) {
        return this.byWorkspace[workspaceId] ?? null
      }
      this.loading[workspaceId] = true
      try {
        const res = await getFinanceAiStatus(workspaceId)
        const data = res?.data
        if (data) {
          this.byWorkspace[workspaceId] = data
          return data
        }
        return null
      } catch {
        // Diagnostic endpoint — a failure must never break the page.
        // Leaving the cache empty keeps the banner hidden (fail-safe:
        // we'd rather not nag than nag on a transient network blip).
        return null
      } finally {
        this.loading[workspaceId] = false
      }
    },
    /** Force a re-fetch, discarding any cached value for the workspace. */
    async refresh(workspaceId: string): Promise<FinanceAiStatus | null> {
      return this.ensure(workspaceId, true)
    },
  },
})

export default useFinanceAiStatusStore
