import { type Ref } from 'vue'
import type { Result } from '@/request/Result'
import { get } from '@/request/index'

/**
 * Finance AI-status API client (Gate 8 Track C).
 * Backend mount: `/admin/api/finance/workspace/<workspace_id>/ai-status`.
 *
 * Reports whether the workspace has an LLM / embedding model configured.
 * When `llm_configured` is false the finance AI features (requirement
 * parsing, summary generation, document ai-fill) silently fall back to
 * deterministic stubs — the FinanceAiBanner surfaces that to the user.
 */

export type FinanceDegradedFeature =
  | 'requirement_parsing'
  | 'summary_generation'
  | 'ai_fill'

export interface FinanceAiStatus {
  /** True iff a usable LLM chat model resolves for the workspace. */
  llm_configured: boolean
  /** Display name of the resolved LLM model, or null when none. */
  llm_model_name: string | null
  /** True iff an EMBEDDING-type model is configured (knowledge matching). */
  embedding_configured: boolean
  /** Features that will degrade to stubs; empty when llm_configured. */
  degraded_features: FinanceDegradedFeature[]
}

const buildUrl = (workspaceId: string) =>
  `/finance/workspace/${workspaceId}/ai-status`

/**
 * GET /finance/workspace/<wid>/ai-status
 */
export const getFinanceAiStatus: (
  workspaceId: string,
  loading?: Ref<boolean>,
) => Promise<Result<FinanceAiStatus>> = (workspaceId, loading) => {
  return get(buildUrl(workspaceId), undefined, loading)
}

export default {
  getFinanceAiStatus,
}
