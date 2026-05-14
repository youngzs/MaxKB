import { type Ref } from 'vue'
import type { Result } from '@/request/Result'
import { get } from '@/request/index'
import type { PageResult } from './type'

/**
 * Finance workflow-run API client (Gate 7 Track B).
 * Backend mount: `/admin/api/finance/workspace/<workspace_id>/workflow-run`.
 *
 * One row per Celery task invocation: parse / match / pack / generate.
 * Used by the per-step progress drawer in materials/detail and the
 * documents wizard to surface real-time runtime status, retry counts,
 * and error messages.
 */

export type WorkflowRunStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'retrying'

export type WorkflowRunTargetType =
  | 'MATERIALS_TASK'
  | 'DOC_GENERATION'
  | 'OTHER'

export interface WorkflowRun {
  id: string
  workspace_id: string
  target_type: WorkflowRunTargetType
  target_id: string
  task_name: string
  celery_task_id: string
  status: WorkflowRunStatus
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  error_message: string
  payload: Record<string, unknown>
  retry_count: number
  created_at: string | null
  updated_at: string | null
}

export interface WorkflowRunListParams {
  target_type?: WorkflowRunTargetType
  target_id?: string
  status?: WorkflowRunStatus
  page?: number
  size?: number
}

const buildUrl = (workspaceId: string) =>
  `/finance/workspace/${workspaceId}/workflow-run`

/**
 * GET /finance/workspace/<wid>/workflow-run?target_type=&target_id=&status=&page=&size=
 */
export const listWorkflowRuns: (
  workspaceId: string,
  params?: WorkflowRunListParams,
  loading?: Ref<boolean>,
) => Promise<Result<PageResult<WorkflowRun>>> = (
  workspaceId,
  params,
  loading,
) => {
  return get(buildUrl(workspaceId), params, loading)
}

export default {
  listWorkflowRuns,
}
