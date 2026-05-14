import { type Ref } from 'vue'
import type { Result } from '@/request/Result'
import { get } from '@/request/index'

/**
 * Finance system-info API client (Gate 7 Track A4 + Gate 8 Track B).
 * Backend mount: `/admin/api/finance/workspace/<workspace_id>/system-info`.
 *
 * ADMIN-only diagnostics envelope. Gate 8 Track B adds the `celery`
 * section — worker liveness + finance task registry — which the audit
 * page surfaces as a small "worker health" card.
 *
 * The endpoint never 500s: individual probes degrade to null/empty, so
 * callers can treat a missing field as "unknown" rather than an error.
 */

export interface CeleryHealth {
  worker_online: boolean
  registered_finance_tasks: string[]
  active_count: number
  queued_estimate: number | null
}

export interface FinanceSystemInfo {
  module_version: string
  workflows_installed: Array<Record<string, unknown>>
  smtp_configs_count: number
  email_templates_count: number
  materials_tasks: Record<string, number>
  projects_count: number
  documents_with_sensitivity: Record<string, number>
  recent_errors: Array<Record<string, unknown>>
  ai_model_configured: boolean
  celery?: CeleryHealth
  deps: Record<string, string>
}

const buildUrl = (workspaceId: string) =>
  `/finance/workspace/${workspaceId}/system-info`

/**
 * GET /finance/workspace/<wid>/system-info
 */
export const getSystemInfo: (
  workspaceId: string,
  loading?: Ref<boolean>,
) => Promise<Result<FinanceSystemInfo>> = (workspaceId, loading) => {
  return get(buildUrl(workspaceId), undefined, loading)
}

export default {
  getSystemInfo,
}
